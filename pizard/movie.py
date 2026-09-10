"""
movie.py -- render the loaded trajectory to a video from PyMOL.

    run ~/viswizard/pizard/movie.py          (or let ~/.pymolrc.py load it)
    PyMOL> pizard_movie out=movie.mp4
    PyMOL> pmovie out=movie.mp4, size=1920x1080, fps=30

Frames are written with cmd.png and muxed with ffmpeg.  It renders headless,
so `pymol -cq` works and no window has to stay in front.

It is deliberately not called `movie`: that name is PyMOL's own module, and
shadowing it would break movie.produce and movie.roll.
"""
import os
import shutil
import subprocess
import tempfile
import time

from pymol import cmd

__all__ = ["pizard_movie"]

HELP = """
pizard_movie -- render the loaded trajectory to a video.

  pizard_movie out=movie.mp4 [options]

  out=FILE       output video                       (default movie.mp4)
  size=WxH       frame size, e.g. 1920x1080         (default: current viewport)
  fps=N          frames per second                  (default 24)
  step=N         render every Nth state             (default 1)
  ray=0|1        ray trace each frame               (default 1)
  keep=1         keep the intermediate PNG frames   (default 0)
  object=NAME    which object sets the state count  (default: the first)

Set the view up first -- orientation, representations, zoom -- the movie uses
exactly what is on screen.
"""


def _viewport():
    try:
        w, h = cmd.get_viewport()
        if w > 0 and h > 0:
            return int(w), int(h)
    except Exception:
        pass
    return 960, 720


def _parse_size(size):
    if not size:
        return _viewport()
    text = str(size).lower().replace("x", " ").replace(",", " ")
    parts = [p for p in text.split() if p]
    if len(parts) != 2:
        raise cmd.QuietException("pizard_movie: size should be WxH, got %r" % size)
    return int(parts[0]), int(parts[1])


def pizard_movie(out="movie.mp4", size="", fps=24, step=1, ray=1, keep=0,
                 object="", quiet=0, _self=cmd):
    if str(out).strip() in ("-h", "help", "?"):
        print(HELP)
        return
    fps, step, ray, keep, quiet = int(fps), int(step), int(ray), int(keep), int(quiet)
    obj = object or (cmd.get_object_list() or [None])[0]
    if obj is None:
        raise cmd.QuietException("pizard_movie: nothing is loaded")

    nstates = cmd.count_states(obj)
    if nstates < 1:
        raise cmd.QuietException("pizard_movie: %s has no states" % obj)

    width, height = _parse_size(size)
    # h264 needs even dimensions
    width -= width % 2
    height -= height % 2

    out = os.path.abspath(os.path.expanduser(out))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="pizard_frames_", dir=os.path.dirname(out))

    if not quiet:
        print("pizard_movie: rendering %d states at %dx%d (every %d)%s"
              % (nstates, width, height, step, "" if ray else ", no ray tracing"))
    t0 = time.time()
    n = 0
    try:
        for state in range(1, nstates + 1, step):
            cmd.frame(state)
            cmd.refresh()
            cmd.png(os.path.join(tmp, "f%05d.png" % n),
                    width=width, height=height, dpi=100, ray=ray)
            n += 1
            if not quiet and n % 25 == 0:
                print("pizard_movie:   %d frames" % n)
        if n == 0:
            raise cmd.QuietException("pizard_movie: no frames were rendered")
        dt = time.time() - t0
        if not quiet:
            print("pizard_movie: rendered %d frames in %.1f s (%.2f s/frame)"
                  % (n, dt, dt / n))

        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            print("pizard_movie: ffmpeg not found -- PNG frames left in %s" % tmp)
            return tmp
        if not quiet:
            print("pizard_movie: encoding %s" % out)
        proc = subprocess.run(
            [ffmpeg, "-y", "-framerate", str(fps), "-i", os.path.join(tmp, "f%05d.png"),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", out],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            print("pizard_movie: ffmpeg failed -- frames kept in %s" % tmp)
            print(proc.stdout.decode("utf-8", "replace")[-2000:])
            return tmp
    finally:
        if keep:
            print("pizard_movie: frames kept in %s" % tmp)
        elif os.path.isdir(tmp) and shutil.which("ffmpeg"):
            shutil.rmtree(tmp, ignore_errors=True)

    if not quiet:
        print("pizard_movie: wrote %s (%d bytes, %d frames @ %d fps)"
              % (out, os.path.getsize(out), n, fps))
    return out


cmd.extend("pizard_movie", pizard_movie)
cmd.extend("pmovie", pizard_movie)
