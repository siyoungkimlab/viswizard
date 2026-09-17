"""
browse.py -- step through the loaded structures from the keyboard.

    run ~/viswizard/pizard/browse.py     (or let ~/.pymolrc.py load it)
    PyMOL> browse                         # s/w, j/k or down/up switch structure
    PyMOL> browse chain L                 # zoom on this selection instead
    PyMOL> browse off                     # stop, and hand the keys back

One structure is shown at a time, zoomed on its ligand, which is the way to
compare several of them when overlaying would just be a thicket.

Keys.  set_key is no use here: it takes only F1-F12, left, right, pgup, pgdn,
home, insert and the CTRL/ALT combinations -- it refuses plain letters, and
while it accepts "up" and "down" it never fires them.  Those page keys are
also spoken for (scenes) and missing from a Mac laptop keyboard.  So the keys
come from a Qt event filter instead, which has to be created and installed in
the GUI thread -- not the thread PyMOL runs commands in.  cmd._call_in_gui_thread
is the GUI's own hook for that.

PyMOL aims the 3D widget's keyboard focus at the command line, which is why
typing in the viewport lands at the prompt -- and why a filter alone would
never see a key.  Wizards drop that focus proxy to get the keyboard; browsing
does the same while it is on, and puts it back afterwards.  The filter also
stands aside whenever a text box has the focus, so clicking the command line
gives you typing and history as usual.
"""
try:
    from pymol import cmd
except ImportError:          # importable, and tested, without PyMOL
    cmd = None

__all__ = ["pizard_browse", "browse_next", "browse_prev"]

# pizard sets this to the --ligand selection it used, so browsing frames the
# same thing the session was set up around.
DEFAULT_SEL = "organic and not resn ACE+NMA+NME"

HELP = """
browse -- step through the loaded structures from the keyboard.

  browse [sel] [, objects] [, buffer] [, keys]

  sel=SEL        what to zoom on in each structure  (default: the ligand
                 pizard used, else organic and not resn ACE+NMA+NME)
  objects=NAMES  which objects to step through      (default: all of them,
                 except a reference loaded by --ref)
  buffer=A       padding around the zoom, angstroms (default 3)
  keys=NEXT PREV also bind these two keys through set_key, e.g. keys="F3 F4"
                 (default: none -- nothing PyMOL already binds is taken)

  browse off     stop, show everything again, and hand the keys back

s or j is the next structure, w or k the previous, and so are the down and up
arrows; all of them wrap around.  They work while the 3D window has the focus,
not while you are typing in the command line.  browse_next and browse_prev
(bnext, bprev) are the same step as a command, wherever the focus is.
A structure where the selection matches nothing is framed whole.
"""

_state = {"objs": [], "i": 0, "sel": "", "buffer": 3.0, "keys": {}, "filter": None}


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


def _install_keys():
    """s/w, j/k and the arrows, through a Qt event filter in the GUI thread."""
    if _state["filter"] is not None:
        return True
    in_gui = getattr(cmd, "_call_in_gui_thread", None)
    if in_gui is None:                      # no Qt GUI: -cq, or an old PyMOL
        return False

    def install():
        import pymol.gui
        from pymol.Qt import QtCore, QtWidgets
        app = QtWidgets.QApplication.instance()
        win = pymol.gui.get_qtwindow()
        if app is None or win is None:
            return None
        Qt = QtCore.Qt
        steps = {Qt.Key_S: 1, Qt.Key_W: -1,        # wasd
                 Qt.Key_J: 1, Qt.Key_K: -1,        # vim
                 Qt.Key_Down: 1, Qt.Key_Up: -1}
        text_widgets = (QtWidgets.QLineEdit, QtWidgets.QTextEdit,
                        QtWidgets.QPlainTextEdit)

        class _Keys(QtCore.QObject):
            def eventFilter(self, obj, ev):
                try:
                    if ev.type() != QtCore.QEvent.KeyPress or not _state["objs"]:
                        return False
                    # never steal from a text box: the command line binds up
                    # and down to its history, and a letter is just a letter
                    if isinstance(app.focusWidget(), text_widgets):
                        return False
                    delta = steps.get(ev.key())
                    if delta and not ev.modifiers():
                        _step(delta)
                        return True
                except Exception:
                    pass
                return False

        filt = _Keys()
        app.installEventFilter(filt)

        # PyMOL aims the 3D widget's keyboard focus at the command line
        # (setFocusProxy in pymol_qt_gui), which is why typing in the viewport
        # lands at the prompt -- and why the filter above would never see a
        # key.  Wizards drop that proxy to get the keyboard; so does browsing,
        # and "browse off" puts it back exactly as it was.
        gl = getattr(win, "pymolwidget", None)
        proxy = gl.focusProxy() if gl is not None else None
        if gl is not None:
            gl.setFocusProxy(None)
            gl.setFocus()
        return (app, filt, gl, proxy)

    try:
        _state["filter"] = in_gui(install)
    except Exception:
        _state["filter"] = None
    return _state["filter"] is not None


def _remove_keys():
    got, _state["filter"] = _state["filter"], None
    if not got:
        return
    app, filt, gl, proxy = got

    def remove():
        app.removeEventFilter(filt)
        if gl is not None:
            gl.setFocusProxy(proxy)
            if proxy is not None:
                proxy.setFocus()

    in_gui = getattr(cmd, "_call_in_gui_thread", None)
    try:
        remove() if in_gui is None else in_gui(remove)
    except Exception:
        pass


def _bind(keys):
    """Optional set_key bindings, for whoever wants a function key as well."""
    for key, delta in zip(keys, (1, -1)):
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
    _remove_keys()


def pizard_browse(sel="", objects="", buffer=3.0, quiet=0, keys=""):
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
    bind = [k for k in str(keys).replace(",", " ").split() if k]
    if bind and len(bind) != 2:
        raise cmd.QuietException("browse: keys= takes two key names, next then"
                                 " previous, e.g. keys=\"F3 F4\"")
    _state.update(objs=names, i=0, sel=str(sel).strip() or DEFAULT_SEL,
                  buffer=float(buffer))
    if bind and not _state["keys"]:
        _bind(bind)
    live = _install_keys()
    _show(quiet)
    if not quiet:
        if live:
            print("browse: s/j next, w/k previous, or the down/up arrows;"
                  " click the command line when you want to type there")
        else:
            print("browse: no Qt window here -- use bnext / bprev, or"
                  " browse keys=\"F3 F4\"")
        if bind:
            print("browse: %s also step, through set_key" % "/".join(bind))
        print("browse: %d structures; 'browse off' when done" % len(names))


def browse_next():
    _step(1)


def browse_prev():
    _step(-1)


if cmd is not None:
    cmd.extend("pizard_browse", pizard_browse)
    cmd.extend("browse", pizard_browse)
    cmd.extend("browse_next", browse_next)
    cmd.extend("browse_prev", browse_prev)
    cmd.extend("bnext", browse_next)
    cmd.extend("bprev", browse_prev)
