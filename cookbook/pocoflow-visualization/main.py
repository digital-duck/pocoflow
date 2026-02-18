"""PocoFlow Visualization -- generate Mermaid diagrams and D3.js visualizations from flows.

Demonstrates: flow introspection, Mermaid diagram generation, D3.js interactive visualization.
"""

import json
import os
import http.server
import socketserver
import threading
import webbrowser
import time
import socket
import click
from pocoflow import Node, Flow


# ---------------------------------------------------------------------------
# Example flow for demonstration
# ---------------------------------------------------------------------------

class ValidateOrder(Node):
    def exec(self, prep_result):
        return "Order validated"
    def post(self, store, prep_result, exec_result):
        store["validated"] = True
        return "default"

class ProcessPayment(Node):
    def exec(self, prep_result):
        return "Payment processed"
    def post(self, store, prep_result, exec_result):
        store["paid"] = True
        return "default"

class ShipOrder(Node):
    def exec(self, prep_result):
        return "Order shipped"
    def post(self, store, prep_result, exec_result):
        store["shipped"] = True
        return "done"


def create_example_flow():
    """Create a simple example flow for visualization."""
    validate = ValidateOrder()
    pay = ProcessPayment()
    ship = ShipOrder()
    validate.then("default", pay)
    pay.then("default", ship)
    return Flow(start=validate)


# ---------------------------------------------------------------------------
# Mermaid diagram generation
# ---------------------------------------------------------------------------

def build_mermaid(flow):
    """Generate a Mermaid diagram string from a Flow."""
    ids, visited, lines = {}, set(), ["graph LR"]
    ctr = 1

    def get_id(n):
        nonlocal ctr
        if n not in ids:
            ids[n] = f"N{ctr}"
            ctr += 1
        return ids[n]

    def link(a, b, action=None):
        if action:
            lines.append(f"    {a} -->|{action}| {b}")
        else:
            lines.append(f"    {a} --> {b}")

    def walk(node, parent=None, action=None):
        if node in visited:
            if parent:
                link(parent, get_id(node), action)
            return
        visited.add(node)

        if isinstance(node, Flow):
            if node.start and parent:
                link(parent, get_id(node.start), action)
            lines.append(f"\n    subgraph sub_{get_id(node)}[{type(node).__name__}]")
            if node.start:
                walk(node.start)
            for act, nxt in node._successors.items():
                if node.start:
                    walk(nxt, get_id(node.start), act)
                else:
                    walk(nxt, None, act)
            lines.append("    end\n")
        else:
            nid = get_id(node)
            lines.append(f"    {nid}['{type(node).__name__}']")
            if parent:
                link(parent, nid, action)
            for act, nxt in node._successors.items():
                walk(nxt, nid, act)

    walk(flow.start if hasattr(flow, 'start') else flow)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# D3.js JSON generation
# ---------------------------------------------------------------------------

def flow_to_json(flow):
    """Convert a Flow to JSON for D3.js visualization."""
    nodes_list, links, ids = [], [], {}
    ctr = 1
    visited = set()

    def get_id(n):
        nonlocal ctr
        if n not in ids:
            ids[n] = ctr
            ctr += 1
        return ids[n]

    def walk(node, parent=None, group=0):
        nid = get_id(node)
        if nid in visited:
            if parent:
                links.append({"source": parent, "target": nid, "action": "default"})
            return
        visited.add(nid)

        if not isinstance(node, Flow):
            nodes_list.append({"id": nid, "name": type(node).__name__, "group": group})
            if parent:
                links.append({"source": parent, "target": nid, "action": "default"})
            for act, nxt in node._successors.items():
                if isinstance(nxt, Flow):
                    walk(nxt, nid, get_id(nxt))
                else:
                    walk(nxt, nid, group)
        else:
            if node.start:
                walk(node.start, parent, nid)
                for act, nxt in node._successors.items():
                    walk(nxt, get_id(node.start), nid)

    start = flow.start if hasattr(flow, 'start') else flow
    if isinstance(start, Flow):
        walk(start)
    else:
        walk(start)

    return {"nodes": nodes_list, "links": links}


# ---------------------------------------------------------------------------
# HTML visualization
# ---------------------------------------------------------------------------

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><title>TITLE</title>
<script src="https://d3js.org/d3.v7.min.js"></script>
<style>
body { font-family: Arial, sans-serif; margin: 0; overflow: hidden; }
svg { width: 100vw; height: 100vh; }
.links line { stroke: #999; stroke-opacity: 0.6; stroke-width: 2px; }
.nodes circle { stroke: #fff; stroke-width: 1.5px; }
.labels { font-size: 12px; pointer-events: none; }
.link-labels { font-size: 10px; fill: #666; pointer-events: none; }
</style></head><body>
<svg id="graph"></svg>
<script>
d3.json("DATA_FILE").then(data => {
    const svg = d3.select("#graph");
    const width = window.innerWidth, height = window.innerHeight;
    const color = d3.scaleOrdinal(d3.schemeCategory10);

    svg.append("defs").append("marker").attr("id","arrow")
        .attr("viewBox","0 -5 10 10").attr("refX",25).attr("refY",0)
        .attr("orient","auto").attr("markerWidth",6).attr("markerHeight",6)
        .append("path").attr("d","M 0,-5 L 10,0 L 0,5").attr("fill","#999");

    const sim = d3.forceSimulation(data.nodes)
        .force("link", d3.forceLink(data.links).id(d => d.id).distance(120))
        .force("charge", d3.forceManyBody().strength(-200))
        .force("center", d3.forceCenter(width/2, height/2))
        .force("collide", d3.forceCollide().radius(40));

    const link = svg.append("g").attr("class","links").selectAll("line")
        .data(data.links).enter().append("line").attr("marker-end","url(#arrow)");
    const node = svg.append("g").attr("class","nodes").selectAll("circle")
        .data(data.nodes).enter().append("circle").attr("r",15)
        .attr("fill", d => color(d.group))
        .call(d3.drag().on("start",(e,d)=>{if(!e.active)sim.alphaTarget(.3).restart();d.fx=d.x;d.fy=d.y})
            .on("drag",(e,d)=>{d.fx=e.x;d.fy=e.y})
            .on("end",(e,d)=>{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null}));
    const label = svg.append("g").attr("class","labels").selectAll("text")
        .data(data.nodes).enter().append("text").text(d=>d.name).attr("text-anchor","middle").attr("dy",25);

    sim.on("tick", () => {
        link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y).attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
        node.attr("cx",d=>d.x).attr("cy",d=>d.y);
        label.attr("x",d=>d.x).attr("y",d=>d.y);
    });
});
</script></body></html>"""


def create_visualization(json_data, output_dir="./viz", name="flow"):
    """Create D3.js visualization files."""
    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, f"{name}.json")
    with open(json_path, "w") as f:
        json.dump(json_data, f, indent=2)

    html = HTML_TEMPLATE.replace("TITLE", f"PocoFlow: {name}").replace("DATA_FILE", f"{name}.json")
    html_path = os.path.join(output_dir, f"{name}.html")
    with open(html_path, "w") as f:
        f.write(html)

    print(f"Visualization saved to {html_path}")
    return html_path


def serve_and_open(html_path):
    """Serve the visualization and open in browser."""
    directory = os.path.dirname(os.path.abspath(html_path))
    filename = os.path.basename(html_path)

    # Find free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    os.chdir(directory)
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", port), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    url = f"http://localhost:{port}/{filename}"
    print(f"Opening {url}")
    webbrowser.open(url)
    return thread, url


@click.command()
@click.option("--no-serve", is_flag=True, help="Don't start HTTP server")
@click.option("--output-dir", default="./viz", help="Output directory")
def main(no_serve, output_dir):
    """Visualize a PocoFlow graph as Mermaid diagram and D3.js interactive chart."""
    flow = create_example_flow()

    print("=== Mermaid Diagram ===\n")
    print(build_mermaid(flow))

    print("\n=== D3.js Visualization ===\n")
    json_data = flow_to_json(flow)
    html_path = create_visualization(json_data, output_dir=output_dir, name="example_flow")

    if not no_serve:
        serve_and_open(html_path)
        print("\nServer running. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nDone.")


if __name__ == "__main__":
    main()
