"""
browse.py -- step through the loaded structures with the up and down arrows.

    run ~/viswizard/pizard/browse.py     (or let ~/.pymolrc.py load it)
    PyMOL> browse                         # up/down now switch structure
    PyMOL> browse chain L                 # zoom on this selection instead
    PyMOL> browse off                     # hand the arrow keys back

One structure is shown at a time, zoomed on its ligand, which is the way to
compare several of them when overlaying would just be a thicket.  PyMOL leaves
up and down unbound (left and right step frames), so nothing is taken away;
whatever was bound is put back by "browse off".

The zoom keeps the current orientation, so every structure is seen from the
same angle -- they have already been superposed by the time you get here.
"""
try:
    from pymol import cmd
except ImportError:          # importable, and tested, without PyMOL
    cmd = None

__all__ = ["pizard_browse"]

# pizard sets this to the --ligand selection it used, so browsing frames the
# same thing the session was set up around.
DEFAULT_SEL = "organic and not resn ACE+NMA+NME"

HELP = """
browse -- step through the loaded structures with the up and down arrows.

  browse [sel] [, objects] [, buffer]

  sel=SEL        what to zoom on in each structure  (default: the ligand
                 pizard used, else organic and not resn ACE+NMA+NME)
  objects=NAMES  which objects to step through      (default: all of them,
                 except a reference loaded by --ref)
  buffer=A       padding around the zoom, angstroms (default 3)

  browse off     stop, show everything again, and give the keys back

Down goes to the next structure, up to the previous one, and both wrap around.
A structure where the selection matches nothing is framed whole.
"""

_state = {"objs": [], "i": 0, "sel": "", "buffer": 3.0, "keys": {}}


def _browsable(objects=""):
    """Objects to step through: everything loaded, minus pizard's reference."""
    if objects:
        return [n for n in str(objects).replace(",", " ").split() if n]
    return [n for n in cmd.get_object_list() if n != "ref"]


def _zoom_target(name, sel):
    """What to frame for one structure: its ligand, or the whole thing."""
    if sel:
        target = "(%s) and (%s)" % (name, sel)
        if cmd.count_atoms(target):
            return target, cmd.count_atoms(target)
    return name, 0


def _show(quiet=0):
    # objects can be deleted while browsing; drop them rather than error
    live = cmd.get_object_list()
    objs = [n for n in _state["objs"] if n in live]
    _state["objs"] = objs
    if not objs:
        print("browse: nothing left to browse -- stopping")
        pizard_browse("off")
        return
    _state["i"] %= len(objs)
    name = objs[_state["i"]]
    for n in objs:
        (cmd.enable if n == name else cmd.disable)(n)
    target, nat = _zoom_target(name, _state["sel"])
    cmd.zoom(target, buffer=_state["buffer"])
    if not quiet:
        print("browse: %d/%d  %-16s %s" % (_state["i"] + 1, len(objs), name,
              "%d atoms in the selection" % nat if nat else "no match -- whole structure"))


def _step(delta):
    if _state["objs"]:
        _state["i"] += delta
        _show()


def _bind():
    for key, delta in (("down", 1), ("up", -1)):
        # remember whatever was there; PyMOL stores bindings in cmd.key_mappings
        _state["keys"][key] = getattr(cmd, "key_mappings", {}).get(key)
        cmd.set_key(key, _step, (delta,))


def _unbind():
    mappings = getattr(cmd, "key_mappings", None)
    for key, prev in _state["keys"].items():
        if mappings is None:
            continue
        if prev is None:
            mappings.pop(key, None)
        else:
            mappings[key] = prev
    _state["keys"] = {}


def pizard_browse(sel="", objects="", buffer=3.0, quiet=0):
    if str(sel).strip() in ("-h", "--help", "help"):
        print(HELP)
        return
    if str(sel).strip().lower() in ("off", "stop"):
        _unbind()
        for n in _state["objs"]:
            cmd.enable(n)
        _state["objs"] = []
        print("browse: off -- every structure is shown again")
        return

    names = _browsable(objects)
    if not names:
        raise cmd.QuietException("browse: no objects are loaded")
    _state.update(objs=names, i=0, sel=str(sel).strip() or DEFAULT_SEL,
                  buffer=float(buffer))
    if not _state["keys"]:
        _bind()
    _show(quiet)
    if not quiet:
        print("browse: down/up for the next/previous of %d structures,"
              " 'browse off' when done" % len(names))


if cmd is not None:
    cmd.extend("pizard_browse", pizard_browse)
    cmd.extend("browse", pizard_browse)
