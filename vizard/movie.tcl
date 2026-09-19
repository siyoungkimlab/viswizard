############################################################
# movie.tcl -- render the loaded trajectory to a video.
#
# Interactively (vizard.tcl sources this, so it is already available):
#
#     vmd sys.pdb traj.dcd -e ~/viswizard/vizard/vizard.tcl -args --ligand "resname LIG"
#     ... rotate/zoom the view by hand ...
#     vmd > vizard_movie -out movie.mp4
#
# Or as a one-shot command line (batch mode triggers on --out):
#
#     vmd -dispdev text sys.pdb traj.dcd -e ~/viswizard/vizard/movie.tcl \
#         -args --ligand "resname LIG" --out movie.mp4 --size 1280 720
#
# Frames are rendered with Tachyon's in-memory renderer (no scene files) and
# muxed with ffmpeg.  Rendering does not need a window: -dispdev text works.
#
# Options (all optional):
#   -out      output video                    (default movie.mp4)
#   -size     {W H}                           (default: current window size)
#   -fps      frames per second               (default 24)
#   -step     render every Nth frame          (default 1)
#   -zoom     scale multiplier, >1 tightens   (default 1)
#   -reframe  1 to re-fit on ligand+pocket    (default 0: keep your view)
#   -keep     1 to keep the TGA frames        (default 0)
############################################################

if {[info exists ::vizard_movie_loaded]} { return }
set ::vizard_movie_loaded 1

proc vizard_movie {args} {
    if {[lsearch -exact $args "-h"] >= 0 || [lsearch -exact $args "-help"] >= 0} {
        puts {
vizard_movie -- render the loaded trajectory to a video (Tachyon + ffmpeg).

  vizard_movie -out movie.mp4 [options]

  -out FILE      output video                      (default movie.mp4)
  -size {W H}    render size                       (default: current window)
  -fps N         frames per second                 (default 24)
  -step N        render every Nth frame            (default 1)
  -zoom F        scale multiplier, >1 tightens     (default 1)
  -reframe 1     re-fit on ligand + pocket         (default 0: keep your view)
  -keep 1        keep the intermediate TGA frames  (default 0)
  -ao 0          render without shadows + ambient occlusion, which is
                 quicker and flatter                (default 1)

Rotate and zoom the view first; by default the movie uses exactly what you see.
}
        return
    }
    array set opt {-out movie.mp4 -size "" -fps 24 -step 1 -zoom 1.0 \
                   -reframe 0 -keep 0 -ao 1 -molid top}
    array set opt $args
    set molid $opt(-molid)
    if {$molid eq "top"} { set molid [molinfo top] }

    set nf [molinfo $molid get numframes]
    if {$nf < 1} { error "vizard_movie: no frames to render" }

    if {$opt(-size) ne ""} {
        lassign $opt(-size) W H
        display resize $W $H
    } else {
        lassign [display get size] W H
    }
    # h264 needs even dimensions
    set W [expr {int($W) - int($W) % 2}] ; set H [expr {int($H) - int($H) % 2}]
    display update

    if {$opt(-reframe) && [info exists ::vizard_reps] \
        && [info commands glue_center] ne ""} {
        glue_center -reps $::vizard_reps
        display update
    }
    if {$opt(-zoom) != 1.0} { scale by $opt(-zoom) ; display update }

    set out [file normalize $opt(-out)]
    set tmp [file join [file dirname $out] "vizard_frames_[pid]"]
    file mkdir $tmp

    # Tachyon renders with whatever the display is set to, and vizard keeps
    # shadows and ambient occlusion off so that redrawing stays quick.  A
    # render is not interactive, so put them back on for the duration -- the
    # movie is what they are for -- and restore them afterwards, error or not.
    set ao_was [display get ambientocclusion]
    set sh_was [display get shadows]
    if {$opt(-ao)} { display shadows on ; display ambientocclusion on }

    puts "movie: rendering $nf frames at ${W}x${H} (every $opt(-step))"
    set t0 [clock milliseconds]
    set i 0
    set rc [catch {
        for {set n 0} {$n < $nf} {incr n $opt(-step)} {
            animate goto $n
            display update
            render TachyonInternal [format "%s/f%05d.tga" $tmp $i]
            incr i
            if {$i % 25 == 0} { puts "movie:   $i frames" }
        }
    } err]
    display shadows $sh_was ; display ambientocclusion $ao_was
    if {$rc} { error $err }
    set dt [expr {([clock milliseconds]-$t0)/1000.0}]
    puts [format "movie: rendered %d frames in %.1f s (%.2f s/frame)" \
          $i $dt [expr {$dt/$i}]]

    set ff [lindex [auto_execok ffmpeg] 0]
    if {$ff eq ""} {
        puts "movie: ffmpeg not found -- TGA frames left in $tmp"
        return $tmp
    }
    puts "movie: encoding $out"
    if {[catch {exec $ff -y -framerate $opt(-fps) -i [file join $tmp f%05d.tga] \
                 -c:v libx264 -pix_fmt yuv420p -crf 18 $out 2>@1} msg]} {
        puts "movie: ffmpeg FAILED -- frames kept in $tmp"
        puts $msg
        return $tmp
    }
    if {$opt(-keep)} { puts "movie: frames kept in $tmp" } else { file delete -force $tmp }
    puts "movie: wrote $out ([file size $out] bytes, $i frames @ $opt(-fps) fps)"
    return $out
}

interp alias {} movie {} vizard_movie

# ---- batch mode: only when --out was passed on the command line ----------
if {[info exists argv] && [lsearch -exact $argv "--out"] >= 0} {
    # Guard on vizard_main, not glue_traj: ~/.vmdrc sources glue.tcl into every
    # session, so glue_traj always exists and vizard.tcl would never be sourced
    # here -- leaving nothing loaded to render.
    if {[info commands vizard_main] eq ""} {
        set cands {}
        if {[info exists env(VIZARD_DIR)]} { lappend cands $env(VIZARD_DIR) }
        catch { lappend cands [file dirname [file normalize [info script]]] }
        lappend cands [file join $env(HOME) viswizard vizard] [pwd]
        foreach d $cands {
            if {$d ne "" && [file exists [file join $d vizard.tcl]]} {
                uplevel #0 [list source [file join $d vizard.tcl]] ; break
            }
        }
    }
    array set A {}
    set key "" ; set buf {}
    foreach tok $argv {
        if {[string match "--*" $tok]} {
            if {$key ne ""} { set A($key) [string trim [join $buf " "]] }
            set key [string range $tok 2 end] ; set buf {}
        } else { lappend buf $tok }
    }
    if {$key ne ""} { set A($key) [string trim [join $buf " "]] }

    set m {}
    foreach {flag key} {-out out -fps fps -step step -zoom zoom -keep keep} {
        if {[info exists A($key)] && $A($key) ne ""} { lappend m $flag $A($key) }
    }
    if {[info exists A(size)] && $A(size) ne ""} { lappend m -size $A(size) }
    # batch has no hand-adjusted view to preserve, so re-fit by default
    if {![info exists A(reframe)]} { lappend m -reframe 1 } \
        else { lappend m -reframe $A(reframe) }
    if {[catch {eval vizard_movie $m} err]} { puts "movie: FAILED -- $err" }
    quit
}
