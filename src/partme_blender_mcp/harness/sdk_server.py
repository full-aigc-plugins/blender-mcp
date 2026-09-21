"""Official MCP SDK transport bridge for the PartMe Blender tool catalog."""

from __future__ import annotations

import hmac
import inspect
import ipaddress
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import anyio
from mcp import types
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import TypeAdapter

from .version import MCP_SERVER_NAME, PRODUCT_NAME, __version__


_CONTENT_ADAPTER = TypeAdapter(types.ContentBlock)
_LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}
MAX_REMOTE_REQUEST_BYTES = 32 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class RemoteServerConfig:
    """Validated configuration for one independently managed remote transport."""

    transport: str
    host: str
    port: int
    streamable_http_path: str = "/mcp"
    sse_path: str = "/sse"
    message_path: str = "/messages/"
    token: str | None = None
    public_url: str | None = None
    issuer_url: str | None = None
    allowed_hosts: tuple[str, ...] = ()
    allowed_origins: tuple[str, ...] = ()
    tls_certfile: str | None = None
    tls_keyfile: str | None = None
    status_file: str | None = None


def _is_loopback(host: str) -> bool:
    if host.lower() in _LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _route(value: str, field: str, *, trailing_slash: bool | None = None) -> None:
    if not value.startswith("/") or value.startswith("//") or "?" in value or "#" in value:
        raise ValueError(f"{field} must be an absolute URL path")
    if trailing_slash is True and not value.endswith("/"):
        raise ValueError(f"{field} must end with '/'")


def validate_remote_config(config: RemoteServerConfig) -> RemoteServerConfig:
    """Reject unsafe listener combinations before a socket is opened."""
    if config.transport not in {"streamable-http", "sse"}:
        raise ValueError("transport must be 'streamable-http' or 'sse'")
    if not config.host or not 1 <= config.port <= 65535:
        raise ValueError("host and port must identify a valid listener")
    _route(config.streamable_http_path, "streamable_http_path")
    _route(config.sse_path, "sse_path")
    _route(config.message_path, "message_path", trailing_slash=True)
    if bool(config.tls_certfile) != bool(config.tls_keyfile):
        raise ValueError("TLS certificate and key must be configured together")

    if not _is_loopback(config.host):
        if not config.token:
            raise ValueError("non-loopback listeners require a bearer token")
        if not config.issuer_url:
            raise ValueError("non-loopback listeners require an OAuth issuer URL")
        if not config.public_url or urlparse(config.public_url).scheme.lower() != "https":
            raise ValueError("non-loopback listeners require an HTTPS public URL")
    if config.public_url and urlparse(config.public_url).scheme.lower() not in {"http", "https"}:
        raise ValueError("public URL must use HTTP or HTTPS")
    return config


def _tool_from_dict(tool: dict) -> types.Tool:
    annotations = tool.get("annotations")
    return types.Tool(
        name=tool["name"],
        title=tool.get("title"),
        description=tool.get("description"),
        inputSchema=tool["inputSchema"],
        outputSchema=tool.get("outputSchema"),
        annotations=types.ToolAnnotations.model_validate(annotations) if annotations else None,
        _meta=tool.get("_meta"),
    )


def _result_from_dict(result: dict) -> types.CallToolResult:
    content = []
    for block in result.get("content", []):
        try:
            content.append(_CONTENT_ADAPTER.validate_python(block))
        except Exception:
            content.append(types.TextContent(text=str(block)))
    return types.CallToolResult(
        content=content,
        structuredContent=result.get("structuredContent"),
        isError=bool(result.get("isError", False)),
    )


def _record_client(adapter, context) -> None:
    session = getattr(context, "session", None)
    params = getattr(session, "client_params", None)
    client = getattr(params, "client_info", None)
    if client is None:
        return
    if hasattr(client, "model_dump"):
        client = client.model_dump(by_alias=True)
    adapter.record_client(client)


def build_official_server(adapter) -> Server:
    """Build one low-level SDK server around the single adapter catalog."""

    async def list_tools(context, params):
        _record_client(adapter, context)
        cursor = getattr(params, "cursor", None) if params is not None else None
        page = await anyio.to_thread.run_sync(lambda: adapter.list_tools(cursor=cursor))
        return types.ListToolsResult(
            tools=[_tool_from_dict(tool) for tool in page["tools"]],
            nextCursor=page.get("nextCursor"),
        )

    async def call_tool(context, params):
        _record_client(adapter, context)
        arguments = params.arguments if isinstance(params.arguments, dict) else {}
        result = await anyio.to_thread.run_sync(lambda: adapter.call_tool(params.name, arguments))
        return _result_from_dict(result)

    server_parameters = inspect.signature(Server).parameters
    if "on_list_tools" in server_parameters:
        return Server(
            MCP_SERVER_NAME,
            version=__version__,
            title=PRODUCT_NAME,
            description="Secure cross-client Blender MCP runtime",
            on_list_tools=list_tools,
            on_call_tool=call_tool,
        )

    # MCP Python SDK 1.x registers low-level handlers through decorators,
    # while SDK 2.x accepts handlers in the constructor. Keep both paths on
    # official public APIs so stdio remains usable in host-managed runtimes.
    server = Server(
        MCP_SERVER_NAME,
        version=__version__,
        instructions="Secure cross-client Blender MCP runtime",
    )

    @server.list_tools()
    async def legacy_list_tools(request: types.ListToolsRequest) -> types.ListToolsResult:
        cursor = getattr(getattr(request, "params", None), "cursor", None)
        page = await anyio.to_thread.run_sync(lambda: adapter.list_tools(cursor=cursor))
        return types.ListToolsResult(
            tools=[_tool_from_dict(tool) for tool in page["tools"]],
            nextCursor=page.get("nextCursor"),
        )

    @server.call_tool(validate_input=False)
    async def legacy_call_tool(name, arguments):
        arguments = arguments if isinstance(arguments, dict) else {}
        result = await anyio.to_thread.run_sync(lambda: adapter.call_tool(name, arguments))
        return _result_from_dict(result)

    return server


async def _run_stdio(adapter) -> None:
    server = build_official_server(adapter)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def serve_stdio(adapter) -> int:
    """Run the official SDK stdio transport until the MCP host closes stdin."""
    anyio.run(_run_stdio, adapter)
    return 0


class StaticTokenVerifier:
    """Constant-time verifier for a user-supplied opaque bearer token."""

    def __init__(self, token: str, resource: str):
        self._token = token
        self._resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        if not hmac.compare_digest(token, self._token):
            return None
        return AccessToken(
            token=token,
            client_id="partme-remote-client",
            scopes=["partme:blender"],
            resource=self._resource,
            subject="partme-remote-client",
        )


def _security(config: RemoteServerConfig) -> TransportSecuritySettings:
    if config.allowed_hosts or config.allowed_origins:
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(config.allowed_hosts),
            allowed_origins=list(config.allowed_origins),
        )
    if _is_loopback(config.host):
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"],
        )
    public = urlparse(config.public_url or "")
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[public.netloc],
        allowed_origins=[f"{public.scheme}://{public.netloc}"],
    )


def _auth(config: RemoteServerConfig) -> tuple[AuthSettings | None, StaticTokenVerifier | None]:
    if not config.token:
        return None, None
    resource = config.public_url or f"http://{config.host}:{config.port}"
    issuer = config.issuer_url or resource
    return (
        AuthSettings(
            issuer_url=issuer,
            resource_server_url=resource,
            required_scopes=["partme:blender"],
            validate_token_resource=True,
        ),
        StaticTokenVerifier(config.token, resource),
    )


def build_remote_app(adapter, config: RemoteServerConfig):
    """Build an official SDK ASGI app for exactly one remote transport."""
    config = validate_remote_config(config)
    server = build_official_server(adapter)
    auth, verifier = _auth(config)
    security = _security(config)
    if config.transport == "streamable-http":
        return ListenerStatusMiddleware(
            _build_streamable_http_app(server, config, auth, verifier, security), config,
        )

    return ListenerStatusMiddleware(_build_sse_app(server, config, auth, verifier, security), config)


def _build_streamable_http_app(server, config, auth, verifier, security):
    """Compose Streamable HTTP from official low-level SDK public APIs."""
    from contextlib import asynccontextmanager

    from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
    from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend, RequireAuthMiddleware
    from mcp.server.auth.routes import build_resource_metadata_url, create_protected_resource_routes
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.authentication import AuthenticationMiddleware
    from starlette.routing import Route

    manager_options = {
        "app": server,
        "json_response": False,
        "stateless": False,
        "security_settings": security,
    }
    # SDK 2.2 exposes a transport-level request limit; the older public
    # constructor does not. Keep the official constructor usable across both
    # shapes while enforcing the limit whenever the SDK provides it.
    if "max_request_body_size" in inspect.signature(StreamableHTTPSessionManager).parameters:
        manager_options["max_request_body_size"] = MAX_REMOTE_REQUEST_BYTES
    manager = StreamableHTTPSessionManager(**manager_options)

    class StreamableHttpApp:
        async def __call__(self, scope, receive, send):
            await manager.handle_request(scope, receive, send)

    endpoint = StreamableHttpApp()
    routes = []
    middleware = []
    if verifier:
        middleware = [
            Middleware(
                AuthenticationMiddleware,
                backend=BearerAuthBackend(
                    verifier,
                    resource_server_url=auth.resource_server_url if auth.validate_token_resource else None,
                ),
            ),
            Middleware(AuthContextMiddleware),
        ]
        metadata_url = build_resource_metadata_url(auth.resource_server_url)
        endpoint = RequireAuthMiddleware(endpoint, auth.required_scopes or [], metadata_url)
    routes.append(Route(config.streamable_http_path, endpoint=endpoint))
    if auth:
        routes.extend(create_protected_resource_routes(
            resource_url=auth.resource_server_url,
            authorization_servers=[auth.issuer_url],
            scopes_supported=auth.required_scopes,
        ))

    @asynccontextmanager
    async def lifespan(_app):
        async with manager.run():
            yield

    return Starlette(routes=routes, middleware=middleware, lifespan=lifespan)


def _build_sse_app(server, config, auth, verifier, security):
    """Compose the deprecated SSE compatibility transport from public SDK APIs."""
    from mcp.server.auth.middleware.auth_context import AuthContextMiddleware
    from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend, RequireAuthMiddleware
    from mcp.server.auth.routes import build_resource_metadata_url, create_protected_resource_routes
    from mcp.server.sse import SseServerTransport
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.authentication import AuthenticationMiddleware
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.routing import Mount, Route

    transport = SseServerTransport(config.message_path, security_settings=security)

    async def handle_sse(scope, receive, send):
        async with transport.connect_sse(scope, receive, send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())
        return Response()

    routes = []
    middleware = []
    if verifier:
        middleware = [
            Middleware(
                AuthenticationMiddleware,
                backend=BearerAuthBackend(
                    verifier,
                    resource_server_url=auth.resource_server_url if auth.validate_token_resource else None,
                ),
            ),
            Middleware(AuthContextMiddleware),
        ]
        metadata_url = build_resource_metadata_url(auth.resource_server_url)
        protected_sse = RequireAuthMiddleware(handle_sse, auth.required_scopes or [], metadata_url)
        protected_messages = RequireAuthMiddleware(
            transport.handle_post_message, auth.required_scopes or [], metadata_url,
        )
        routes.extend([
            Route(config.sse_path, endpoint=protected_sse, methods=["GET"]),
            Mount(config.message_path, app=protected_messages),
        ])
    else:
        async def sse_endpoint(request: Request) -> Response:
            return await handle_sse(request.scope, request.receive, request._send)

        routes.extend([
            Route(config.sse_path, endpoint=sse_endpoint, methods=["GET"]),
            Mount(config.message_path, app=transport.handle_post_message),
        ])
    if auth:
        routes.extend(create_protected_resource_routes(
            resource_url=auth.resource_server_url,
            authorization_servers=[auth.issuer_url],
            scopes_supported=auth.required_scopes,
        ))
    return Starlette(routes=routes, middleware=middleware)


class ListenerStatusMiddleware:
    """Track active transport sessions and publish a local status snapshot."""

    def __init__(self, app, config: RemoteServerConfig):
        self.app = app
        self.config = config
        self.http_clients = 0
        self.sse_clients = 0

    def _write(self, state: str = "running") -> None:
        if not self.config.status_file:
            return
        target = Path(self.config.status_file)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "state": state,
            "transport": self.config.transport,
            "clients": self.http_clients if self.config.transport == "streamable-http" else self.sse_clients,
            "pid": os.getpid(),
        }
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
        temporary.replace(target)

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            async def lifespan_send(message):
                if message["type"] == "lifespan.startup.complete":
                    self._write("running")
                elif message["type"] == "lifespan.shutdown.complete":
                    self._write("stopped")
                await send(message)
            return await self.app(scope, receive, lifespan_send)

        path = scope.get("path", "")
        method = scope.get("method", "")
        if (self.config.transport == "streamable-http" and method == "GET"
                and path == self.config.streamable_http_path):
            # The official client keeps one GET stream open for the lifetime of
            # a connected session. Count that live stream instead of issued
            # session IDs: session IDs otherwise remain stale when a client
            # disconnects unexpectedly or its DELETE arrives concurrently.
            self.http_clients += 1
            self._write()
            try:
                return await self.app(scope, receive, send)
            finally:
                self.http_clients = max(0, self.http_clients - 1)
                self._write()

        if self.config.transport == "sse" and method == "GET" and path == self.config.sse_path:
            self.sse_clients += 1
            self._write()
            try:
                return await self.app(scope, receive, send)
            finally:
                self.sse_clients = max(0, self.sse_clients - 1)
                self._write()

        await self.app(scope, receive, send)


def serve_remote(adapter, config: RemoteServerConfig) -> int:
    """Run one remote listener; HTTP and SSE use separate processes/lifecycles."""
    import uvicorn

    config = validate_remote_config(config)
    app = build_remote_app(adapter, config)
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        ssl_certfile=config.tls_certfile,
        ssl_keyfile=config.tls_keyfile,
        log_level="info",
    )
    return 0
