---
name: Flask preview routing
description: Replit routing behavior for a standalone Flask workflow in a multi-artifact workspace.
---

A healthy Flask workflow can listen on `0.0.0.0:5000` and return HTTP 200 locally while the default `.replit.dev` domain routes to an existing artifact service and returns 404.

**Why:** this workspace's default domain is controlled by the application artifact router, while the Flask server runs as a separate webview workflow.

**How to apply:** Check the workflow's open port and local response. In Replit Preview, use the domain/port selector to choose port 5000. Avoid adding a partial `.replit` `[[ports]]` list; artifact services require complete port representation, and the mapping does not override the application router here.
