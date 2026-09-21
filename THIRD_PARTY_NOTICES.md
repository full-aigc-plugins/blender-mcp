# Third-Party Notices

Blender and other product names identify interoperability targets. Their trademarks and
software remain the property of their respective owners.

This repository does not redistribute Blender, ffmpeg, a vendor uploader, or another product's
private runtime. Users install Blender separately from its official distribution.

## Model Context Protocol Python SDK

The public stdio, Streamable HTTP, and compatibility SSE transports depend on the official
`mcp` Python package from https://github.com/modelcontextprotocol/python-sdk, version `>=2.2.0,<3`.
It is installed by the Python package manager and is licensed under the MIT License.

## blender_mcp_community (vendored community Add-on)

`vendor/community/blender_mcp_community/__init__.py` is a verbatim copy of `addon.py` from
https://github.com/ahujasid/blender-mcp (commit 6f992ffbca, upstream version 2.0.0).

Copyright © 2025 Siddharth Ahuja

Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify, merge,
publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons
to whom the Software is furnished to do so, subject to the following conditions: The above
copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
USE OR OTHER DEALINGS IN THE SOFTWARE.

## Tencent Cloud Python SDK (vendored for Blender)

The Blender Add-on archive includes the `tencentcloud` package trees from
`tencentcloud-sdk-python-ai3d` 3.1.57 and `tencentcloud-sdk-python-common` 3.1.57.
Source: https://github.com/TencentCloud/tencentcloud-sdk-python

Copyright © 2017–2026 Tencent Cloud. Licensed under the Apache License, Version 2.0.
The complete license text and exact wheel provenance are included under
`vendor/tencentcloud_sdk/` in the source tree and `partme_blender_mcp/_vendor/` in the
assembled Add-on.
