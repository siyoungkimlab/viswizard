#!/bin/bash
# Install the viswizard commands:
#   vizard  -> VMD    (viswizard/vizard)
#   pizard  -> PyMOL  (viswizard/pizard)
set -e
VIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN="${1:-$HOME/.local/bin}"
mkdir -p "$BIN"

# ---------------------------------------------------------------- vizard (VMD)
cat > "$BIN/vizard" <<WRAP
#!/bin/bash
# vizard -- glue + align + view a protein/ligand trajectory in VMD.
#   vizard sys.pdb traj.dcd --ligand "resname LIG"
#   vizard sys.dms traj.dcd --ligand "resname LIG"     (DMS converted for you)
#   vizard sys.pdb traj.dcd --ligand "resname LIG" --out movie.mp4
#   vizard --help
VIZARD_DIR="$VIZ/vizard"
export VIZARD_DIR

VMD=""
for c in vmd \\
  /Applications/VMD*.app/Contents/vmd2/lib/vmd_MACOSX* \\
  /Applications/VMD*.app/Contents/MacOS/startup.command ; do
  if command -v "\$c" >/dev/null 2>&1; then VMD="\$c"; break; fi
  if [ -x "\$c" ]; then VMD="\$c"; break; fi
done
[ -n "\$VMD" ] || { echo "vizard: cannot find vmd" >&2; exit 1; }

files=(); flags=(); vmdargs=()
while [ \$# -gt 0 ]; do
  case "\$1" in
    --*) flags+=("\$1") ;;
    -dispdev|-size|-pos|-startup) vmdargs+=("\$1" "\$2"); shift ;;
    -*)  if [ \${#flags[@]} -gt 0 ]; then flags+=("\$1"); else vmdargs+=("\$1"); fi ;;
    *)   if [ \${#flags[@]} -gt 0 ]; then flags+=("\$1"); else files+=("\$1"); fi ;;
  esac
  shift
done

# VMD has no DMS plugin and cannot read .cms: convert to MAE on the way in
conv=()
for f in "\${files[@]}"; do
  case "\$f" in
    *.dms|*.DMS|*.cms|*.CMS)
      [ -f "\$f" ] || { echo "vizard: no such file: \$f" >&2; exit 1; }
      cache="\$HOME/.viswizard_cache"; mkdir -p "\$cache"
      base="\$(basename "\$f")"; out="\$cache/\${base%.*}.mae"
      if [ ! -f "\$out" ] || [ "\$f" -nt "\$out" ]; then
        PY=""; for c in python3 python; do command -v "\$c" >/dev/null 2>&1 && { PY="\$c"; break; }; done
        [ -n "\$PY" ] || { echo "vizard: need python3 to read \$f" >&2; exit 1; }
        "\$PY" "$VIZ/pizard/formats.py" "\$f" "\$out" >/dev/null \\
          || { echo "vizard: could not convert \$f" >&2; exit 1; }
        echo "vizard: converted \$f -> \$out"
      fi
      conv+=("\$out") ;;
    *) conv+=("\$f") ;;
  esac
done
files=("\${conv[@]}")

script="\$VIZARD_DIR/vizard.tcl"; dispdev=()
for f in "\${flags[@]}"; do
  [ "\$f" = "--out" ] && { script="\$VIZARD_DIR/movie.tcl"; dispdev=(-dispdev text); }
  { [ "\$f" = "--help" ] || [ "\$f" = "-h" ]; } && dispdev=(-dispdev text)
done

# Pass files through --args, not on VMD's command line: vmd puts every file
# given to it into ONE molecule, which is wrong for several systems.
exec "\$VMD" "\${dispdev[@]}" "\${vmdargs[@]}" -e "\$script" \\
     -args --files "\${files[@]}" "\${flags[@]}"
WRAP
chmod +x "$BIN/vizard"
echo "installed: $BIN/vizard  -> VMD    ($VIZ/vizard)"

# -------------------------------------------------------------- pizard (PyMOL)
cat > "$BIN/pizard" <<WRAP
#!/bin/bash
# pizard -- glue + align + view a protein/ligand trajectory in PyMOL.
#   pizard sys.pdb traj.dcd --ligand "resn LIG"
#   pizard sys.dms --ligand "resn LIG"
#   pizard --help
# NOTE: PyMOL selection syntax, not VMD's: resn/resi/polymer, and "resi 1-40".
PIZARD_DIR="$VIZ/pizard"
export PIZARD_DIR

PM=""
for c in pymol /Applications/PyMOL.app/Contents/bin/pymol ; do
  if command -v "\$c" >/dev/null 2>&1; then PM="\$c"; break; fi
  if [ -x "\$c" ]; then PM="\$c"; break; fi
done
[ -n "\$PM" ] || { echo "pizard: cannot find pymol" >&2; exit 1; }

files=(); flags=(); pmargs=()
while [ \$# -gt 0 ]; do
  case "\$1" in
    --help|-h) exec "\$PM" -cq "\$PIZARD_DIR/pizard.py" -- --help ;;
    --*) flags+=("\$1") ;;
    -*)  if [ \${#flags[@]} -gt 0 ]; then flags+=("\$1"); else pmargs+=("\$1"); fi ;;
    *)   if [ \${#flags[@]} -gt 0 ]; then flags+=("\$1"); else files+=("\$1"); fi ;;
  esac
  shift
done
[ \${#files[@]} -gt 0 ] || { echo "pizard: no input file given" >&2; exit 1; }

# rendering a video needs no window, and should exit when it is done
for f in "\${flags[@]}"; do [ "\$f" = "--out" ] && pmargs=(-cq "\${pmargs[@]}"); done

exec "\$PM" "\${pmargs[@]}" "\$PIZARD_DIR/pizard.py" -- "\${files[@]}" "\${flags[@]}"
WRAP
chmod +x "$BIN/pizard"
echo "installed: $BIN/pizard  -> PyMOL  ($VIZ/pizard)"

# ------------------------------------------------------------------- ~/.vmdrc
RC="$HOME/.vmdrc"
if ! grep -qs "VMDDIR" "$RC" 2>/dev/null; then
  tmp="$(mktemp)"
  cat > "$tmp" <<'HDR'
# Load VMD's own defaults first: a user ~/.vmdrc is read INSTEAD of the
# system one, and that is where "menu main on" comes from.
if {[info exists env(VMDDIR)] && [file exists [file join $env(VMDDIR) .vmdrc]]} {
    source [file join $env(VMDDIR) .vmdrc]
} else {
    light 0 on
    light 1 on
    axes location lowerleft
    stage location off
    menu main on
}
HDR
  [ -f "$RC" ] && cat "$RC" >> "$tmp"
  mv "$tmp" "$RC"
  echo "prepended VMD defaults to $RC (keeps the Main menu)"
fi
# Replace our block between markers.  (Trying to be clever with grep -v and a
# list of patterns mangles the block on the second run -- it strips lines out
# of the very thing it wrote the first time.)
strip_block() {   # strip_block <file> <marker>
  [ -f "$1" ] || return 0
  awk -v m="$2" 'index($0, ">>> " m " >>>"){skip=1} !skip{print} index($0, "<<< " m " <<<"){skip=0}' \
      "$1" > "$1.tmp" && mv "$1.tmp" "$1"
}

strip_block "$RC" viswizard
{ echo "# >>> viswizard >>>"
  for f in glue movie formats align view; do echo "source $VIZ/vizard/$f.tcl"; done
  echo "# <<< viswizard <<<"
} >> "$RC"
echo "refreshed: $RC"

# ---------------------------------------------------------------- ~/.pymolrc.py
PRC="$HOME/.pymolrc.py"
strip_block "$PRC" viswizard
cat >> "$PRC" <<PRCEOF
# >>> viswizard >>>
# DMS reader/writer, MAE writer, the MAE reader for open-source PyMOL (so
# 'load x.dms' and 'save x.dms' just work), the movie command, and 'browse'.
import os as _os, sys as _sys
_vw = "$VIZ/pizard"
if _os.path.isdir(_vw):
    if _vw not in _sys.path:
        _sys.path.insert(0, _vw)
    try:
        import mae_reader, formats, movie, browse
    except Exception as _e:
        print("viswizard: could not load format handlers: %s" % _e)
# <<< viswizard <<<
PRCEOF
echo "refreshed: $PRC"

case ":$PATH:" in
  *":$BIN:"*) ;;
  *) echo "NOTE: $BIN is not on your PATH; add it to ~/.bashrc" ;;
esac
