"""A fake `gh api` for tests/test_release_publish.py. State lives in $MOCK_STATE (a JSON file)."""
import json, os, re, sys
from pathlib import Path

state_path = Path(os.environ["MOCK_STATE"])
state = json.loads(state_path.read_text())
log = Path(str(state_path) + ".log")
args = sys.argv[1:]
log.open("a").write(" ".join(args) + "\n")
assert args[0] == "api", args
args = args[1:]
method, headers, fields, jq, input_file, paginate = "GET", [], {}, None, None, False
endpoint = None
i = 0
while i < len(args):
    a = args[i]
    if a == "-X": method = args[i + 1]; i += 2; continue
    if a == "-H": headers.append(args[i + 1]); i += 2; continue
    if a in ("-f", "-F"):
        k, v = args[i + 1].split("=", 1)
        if v.startswith("@"): v = Path(v[1:]).read_text()
        fields[k] = v; i += 2; continue
    if a == "--jq": jq = args[i + 1]; i += 2; continue
    if a == "--input": input_file = args[i + 1]; i += 2; continue
    if a == "--paginate": paginate = True; i += 1; continue
    if a == "--silent": i += 1; continue
    endpoint = a; i += 1
repo = os.environ["DOWNLOADS_REPO"]

def out(obj): print(obj if isinstance(obj, str) else json.dumps(obj))
def save(): state_path.write_text(json.dumps(state))
def notfound(): print('{"message":"Not Found"}', file=sys.stderr); print("gh: Not Found (HTTP 404)", file=sys.stderr); sys.exit(1)

if state.get("auth_fail"):
    print("gh: Bad credentials (HTTP 401)", file=sys.stderr); sys.exit(1)
if endpoint == f"repos/{repo}":
    out(repo); sys.exit(0)
m = re.fullmatch(rf"repos/{re.escape(repo)}/releases/tags/(.+)", endpoint or "")
if m:
    rel = [r for r in state["releases"] if r["tag_name"] == m.group(1) and not r["draft"]]
    if rel: out(rel[0]); sys.exit(0)
    notfound()
m = re.fullmatch(rf"repos/{re.escape(repo)}/git/ref/tags/(.+)", endpoint or "")
if m:
    if m.group(1) in state["tags"]: out({"ref": "refs/tags/" + m.group(1)}); sys.exit(0)
    notfound()
if endpoint == f"repos/{repo}/releases" and method == "GET":
    tag = re.search(r'tag_name == \\?"([^"\\]+)', jq).group(1)
    for r in state["releases"]:
        if r["draft"] and r["tag_name"] == tag: print(r["id"])
    sys.exit(0)
m = re.fullmatch(rf"repos/{re.escape(repo)}/releases/(\d+)", endpoint or "")
if m and method == "DELETE":
    state["releases"] = [r for r in state["releases"] if r["id"] != int(m.group(1))]; save(); sys.exit(0)
if endpoint == f"repos/{repo}/releases" and method == "POST":
    rid = 1000 + len(state["releases"])
    rel = {"id": rid, "tag_name": fields["tag_name"], "name": fields["name"], "body": fields["body"],
           "draft": fields["draft"] == "true", "prerelease": fields["prerelease"] == "true", "assets": [],
           "target_commitish": fields["target_commitish"]}
    state["releases"].append(rel); save(); out(rel); sys.exit(0)
m = re.fullmatch(r"https://uploads\.github\.com/repos/[^/]+/[^/]+/releases/(\d+)/assets\?name=(.+)", endpoint or "")
if m and method == "POST":
    rel = next(r for r in state["releases"] if r["id"] == int(m.group(1)))
    data = Path(input_file).read_bytes()
    if state.get("corrupt_upload") and m.group(2).endswith(".zip"):
        data = data[:-1] + b"X"
    aid = 5000 + sum(len(r["assets"]) for r in state["releases"])
    store = state_path.parent / f"asset-{aid}"
    store.write_bytes(data)
    rel["assets"].append({"id": aid, "name": m.group(2)}); save(); out(m.group(2)); sys.exit(0)
m = re.fullmatch(rf"repos/{re.escape(repo)}/releases/(\d+)/assets", endpoint or "")
if m:
    rel = next(r for r in state["releases"] if r["id"] == int(m.group(1)))
    for a in rel["assets"]: print(f'{a["id"]} {a["name"]}')
    sys.exit(0)
m = re.fullmatch(rf"repos/{re.escape(repo)}/releases/assets/(\d+)", endpoint or "")
if m:
    sys.stdout.buffer.write((state_path.parent / f"asset-{m.group(1)}").read_bytes()); sys.exit(0)
m = re.fullmatch(rf"repos/{re.escape(repo)}/releases/(\d+)", endpoint or "")
if m and method == "PATCH":
    rel = next(r for r in state["releases"] if r["id"] == int(m.group(1)))
    rel["draft"] = fields["draft"] != "false"
    if not rel["draft"]: state["tags"].append(rel["tag_name"])
    save()
    out({**rel, "html_url": f"https://github.com/{repo}/releases/tag/{rel['tag_name']}",
         "immutable": state.get("immutable", False)})
    sys.exit(0)
print(f"mock gh: unhandled {method} {endpoint}", file=sys.stderr); sys.exit(2)
