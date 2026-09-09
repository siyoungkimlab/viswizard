############################################################
# vizard.tcl -- glue + align + set up a view, at VMD start-up:
#
#   vmd sys.pdb traj.dcd -e ~/viswizard/vizard/vizard.tcl -args "resname LIG"
#
# Use the FULL path to this script: if VMD cannot open the -e file it prints
# one ERROR line and then shows you the raw trajectory, which looks exactly
# like the problem you were trying to fix.
#
# Two VMD behaviours this script defends against:
#   * -args is split into words in GUI mode but kept whole in -dispdev text,
#     so the selection must be rebuilt with [join $argv].
#   * -e does NOT stop on error; it runs the next command regardless.  All
#     the work therefore happens inside a proc, so a failure aborts it and
#     cannot be followed by a bogus "ready" message.
############################################################

proc vizard_help {} {
    puts {
vizard -- glue a ligand to its protein across PBC, align, and set up a view.

  vizard file [file ...] [options]

A structure -- or a bare 4-character PDB id -- starts a new molecule, and any
trajectories after it attach to it.  Each molecule gets its own colour and is
superposed onto the first:

  vizard a.pdb a.dcd b.pdb b.dcd 3ptb --ligand "resname LIG" --ref 1ubq

Options (all optional; values may contain spaces):

  --ligand SEL   ligand selection, used for reps, colouring, pocket and the
                 view centre                      (default "resname LIG")
  --glue SEL     what is held together across the periodic boundary
                                                  (default "protein or (<ligand>)")
  --align SEL    what the trajectory is fitted on (default "protein and name CA")
  --pocket A     pocket residue distance cutoff, angstroms      (default 6)
  --ref FILE|ID  reference structure, a file or a 4-character PDB id (fetched
                 and cached in ~/.viswizard_cache).  Fitted internally
                 first, then put onto the reference by sequence alignment,
                 so residue numbering need not match.

  --lig, --fit are accepted as aliases for --ligand, --align.
  With no flags at all, everything is taken as the ligand selection.

Examples:

  -args "resname LIG"
  -args --ligand "resname UNK" --pocket 8
  -args --glue "protein or resname LIG" --align "protein and name CA and resid 145 to 149"

Note: VMD needs "resid 145 to 149".  "resid 145-149" is a syntax error.

Then, at the vmd> prompt:

  vizard_movie -out movie.mp4        render the trajectory to a video
  vizard_movie -h                    movie options
  glue_center -reps {1 2}            re-frame on ligand + pocket
  glue_strip -sel "protein or resname LIG" -o solute
                                     write a small, already-glued trajectory
  vizard_load_dms sys.dms            load a DMS file (VMD has no DMS plugin)
  vizard_write_mae SEL out.mae       write MAE (VMD's own plugin is read-only)
  vizard_write_dms SEL out.dms       write DMS
  fetch 1ubq                         download a PDB entry, load it, and apply
                                     the standard reps (alias: vizard_fetch)
  mm 1 0                             superpose molid 1 onto molid 0 by sequence;
                                     numbering need not match
                                     (aliases: matchmaker, vizard_matchmaker)
  reps 0                             re-apply the standard reps to a molid
  view 1 0                           frame the view on rep 1 of molid 0
                                     (aliases: focuson, zoomto)
  viewsel "resid 45"                 frame on any selection
  pick on                            shift + left-click an atom to focus it
  movie -out movie.mp4               render a video (alias: vizard_movie)

Each fetched molecule gets its own colour pair: a muted protein and a bright
ligand, so several structures stay distinguishable.
}
}

proc vizard_main {} {
    global argv env

    set cands {}
    if {[info exists env(VIZARD_DIR)]} { lappend cands $env(VIZARD_DIR) }
    catch { lappend cands [file dirname [file normalize [info script]]] }
    lappend cands [file join $env(HOME) viswizard vizard] [pwd]
    set glue ""
    foreach d $cands {
        if {$d ne "" && [file exists [file join $d glue.tcl]]} {
            set glue [file join $d glue.tcl]; break
        }
    }
    if {$glue eq ""} {
        error "cannot find glue.tcl (looked in: $cands); set VIZARD_DIR"
    }
    uplevel #0 [list source $glue]
    if {[info commands glue_traj] eq ""} {
        error "sourced $glue but glue_traj is undefined"
    }
    foreach _f {movie formats align view} {
        catch { uplevel #0 [list source [file join [file dirname $glue] $_f.tcl]] }
    }
    puts "vizard: using $glue"

    # Arguments.  GUI mode splits -args into words while -dispdev text keeps
    # them whole, so rebuild each value by joining the words that follow its
    # flag.  Both shapes give the same result.
    #
    #   -args --ligand "resname LIG"
    #   -args --glue "protein or resname LIG" --align "protein and name CA"
    #   -args --align "protein and name CA and resid 145 to 149"
    #
    # With no flags at all, everything is taken as the ligand selection.
    # NOTE: VMD wants "resid 145 to 149"; "resid 145-149" is a syntax error.
    if {[info exists argv] && ([lsearch -exact $argv "--help"] >= 0 ||
                               [lsearch -exact $argv "-h"] >= 0)} {
        vizard_help
        set ::vizard_help_only 1
        return
    }

    # A load that fails leaves no molecule at all, and a load that was never
    # attempted looks identical, so say what to check rather than guessing.
    array set A {}
    set key "" ; set buf {}
    if {[info exists argv]} {
        foreach tok $argv {
            if {[string match "--*" $tok]} {
                if {$key ne ""} { set A($key) [string trim [join $buf " "]] }
                set key [string range $tok 2 end] ; set buf {}
            } else {
                lappend buf $tok
            }
        }
        if {$key ne ""} {
            set A($key) [string trim [join $buf " "]]
        } elseif {[llength $buf] > 0} {
            set A(ligand) [string trim [join $buf " "]]
        }
    }
    foreach {alias real} {lig ligand fit align} {
        if {[info exists A($alias)] && ![info exists A($real)]} { set A($real) $A($alias) }
    }

    # A misspelt flag would otherwise be dropped in silence and you would get
    # the default selection while believing you had overridden it.
    set known {ligand lig glue align fit pocket out ref size fps step zoom keep reframe files}
    foreach k [lsort [array names A]] {
        if {[lsearch -exact $known $k] < 0} {
            error "unknown option '--$k'; known options are --[join [lsort $known] { --}]"
        }
    }

    set ligsel "resname LIG"
    if {[info exists A(ligand)] && $A(ligand) ne ""} { set ligsel $A(ligand) }
    set gluesel "protein or ($ligsel)"
    if {[info exists A(glue)] && $A(glue) ne ""} { set gluesel $A(glue) }
    set alignsel "protein and name CA"
    if {[info exists A(align)] && $A(align) ne ""} { set alignsel $A(align) }
    set pocketcut 6.0
    if {[info exists A(pocket)] && $A(pocket) ne ""} {
        if {![string is double -strict $A(pocket)] || $A(pocket) <= 0} {
            error "--pocket must be a positive number, got '$A(pocket)'"
        }
        set pocketcut $A(pocket)
    }

    # ---- load ---------------------------------------------------------------
    # A structure (or a bare 4-character PDB id) starts a new molecule; any
    # trajectories after it attach to it.  Loading here rather than on VMD's
    # command line matters: files given to vmd directly all go into ONE
    # molecule, which is wrong for several systems.
    set mols {}
    if {[info exists A(files)] && $A(files) ne ""} {
        set TRAJ {dcd xtc trr dtr nc netcdf crd trj}
        set groups {}
        foreach f $A(files) {
            set ext [string tolower [string trimleft [file extension $f] .]]
            if {[lsearch -exact $TRAJ $ext] >= 0 && [llength $groups] > 0} {
                set last [lindex $groups end]
                lset groups end [list [lindex $last 0] \
                                      [concat [lindex $last 1] [list $f]]]
            } else {
                lappend groups [list $f {}]
            }
        }
        foreach g $groups {
            lassign $g top trajs
            if {[file exists $top]} {
                set m [mol new $top waitfor all]
            } elseif {[regexp {^[0-9][0-9A-Za-z]{3}$} $top]} {
                set m [vizard_fetch $top -noreps]
            } else {
                error "no such file, and '$top' is not a 4-character PDB id: $top"
            }
            foreach t $trajs { mol addfile $t waitfor all $m }
            # frame 0 is the topology's own coordinates; drop it when a
            # trajectory was loaded on top
            if {[llength $trajs] && [molinfo $m get numframes] > 1} {
                animate delete beg 0 end 0 $m
            }
            lappend mols $m
            puts [format "vizard: %-16s molid %-3s %6d atoms, %3d frames" \
                  [file tail $top] $m [molinfo $m get numatoms] \
                  [molinfo $m get numframes]]
        }
    } else {
        if {[molinfo num] == 0} {
            error "no molecule is loaded.  Use the 'vizard' wrapper, or give\
                   files to vmd before -e."
        }
        set mols [list [molinfo top]]
        if {[molinfo top get numframes] > 1} { animate delete beg 0 end 0 top }
    }
    mol top [lindex $mols 0]

    foreach {label sel} [list ligand $ligsel glue $gluesel align $alignsel] {
        if {[catch {atomselect top "$sel"} s]} {
            error "$label selection '$sel' is not valid VMD syntax: $s"
        }
        set n [$s num] ; $s delete
        if {$n == 0} { error "$label selection '$sel' matched 0 atoms" }
        puts [format "vizard: %-6s %-44s %6d atoms" $label "'$sel'" $n]
    }

    # ---- glue + internal alignment, per molecule ---------------------------
    foreach m $mols {
        set nl [[atomselect $m "$ligsel"] num]
        set na [[atomselect $m "$alignsel"] num]
        if {$na < 3} {
            puts "vizard: molid $m -- align selection matches $na atoms, skipping"
            continue
        }
        set g $gluesel
        if {$nl == 0} {
            set g "protein"
            puts "vizard: molid $m -- no ligand matched; gluing protein only"
        }
        glue_traj -molid $m -glue $g -align $alignsel -quiet [expr {[llength $mols] > 1}]
    }

    # Optional reference structure.  glue_traj has already fitted every frame
    # onto frame 0, so putting frame 0 onto the reference and applying the same
    # transform to every frame carries the whole trajectory with it.
    if {[info exists A(ref)] && $A(ref) ne ""} {
        set trajmol [lindex $mols 0]
        # --ref takes a file OR a 4-character PDB id, which is fetched (cached)
        if {[file exists $A(ref)]} {
            set refmol [mol new $A(ref) waitfor all]
        } elseif {[regexp {^[0-9][0-9A-Za-z]{3}$} $A(ref)]} {
            if {[info commands vizard_fetch] eq ""} {
                error "--ref '$A(ref)' looks like a PDB id but align.tcl is not loaded"
            }
            set refmol [vizard_fetch $A(ref) -noreps]
        } else {
            error "--ref: no such file, and '$A(ref)' is not a 4-character PDB id"
        }
        mol top $trajmol
        if {[catch {vizard_matchmaker $trajmol $refmol -sel $alignsel \
                                      -allframes 1} err]} {
            puts "vizard: WARNING -- could not align onto the reference: $err"
        }
        # show the reference as a faint cartoon
        while {[molinfo $refmol get numreps] > 0} { mol delrep 0 $refmol }
        mol representation NewCartoon 0.30 20.0 4.1 0
        mol selection "protein"
        mol color ColorID 6
        mol material Transparent
        mol addrep $refmol
        mol top $trajmol
        puts "vizard: reference '$A(ref)' loaded as molid $refmol"
    }

    # put every other molecule onto the first
    foreach m [lrange $mols 1 end] {
        if {[catch {vizard_matchmaker $m [lindex $mols 0] -sel $alignsel \
                                      -allframes 1} err]} {
            puts "vizard: WARNING -- could not superpose molid $m: $err"
        }
    }

    set p [atomselect top "protein" frame 0]
    set l [atomselect top "$ligsel" frame 0]
    set n [llength [lindex [measure contacts 5.0 $p $l] 0]]
    $p delete; $l delete
    if {$n == 0} {
        puts "vizard: WARNING -- no protein/ligand contacts within 5 A in"
        puts "vizard:            frame 0; is the ligand actually bound?"
    } else {
        puts "vizard: OK -- $n protein/ligand contacts within 5 A in frame 0"
    }

    if {[llength $mols] > 1} {
        # several systems: give each its own colour scheme rather than the
        # single-molecule look, so they can be told apart
        display projection Orthographic
        display rendermode GLSL
        display depthcue on
        display culling off
        display antialias on
        display backgroundgradient off
        color Display Background black
        axes location Off
        foreach m $mols {
            catch { vizard_reps $m -ligand $ligsel -pocket $pocketcut }
        }
        set ::vizard_reps [list 1 2]
        catch { glue_center -molid [lindex $mols 0] -reps {1 2} }
    } else {
        # Orthographic: no perspective foreshortening, so distances read true.
        display projection Orthographic

        # ---- display: matte ambient-occlusion look on white -------------------
        # Background is black, so depth cueing fogs toward black and distant atoms
        # darken -- the classic VMD look.  For a publication-style white figure,
        # set Background to white AND change Element/Name H to gray, or the
        # hydrogens vanish.  Everything below is cosmetic and safe to delete.
        # Depth cueing fogs toward the background colour -- tune with
        # "display cuemode Linear|Exp|Exp2", cuedensity, cuestart, cueend.
        display projection Orthographic
        display rendermode GLSL
        display depthcue on
        display culling off
        display antialias on
        display shadows on
        display ambientocclusion on
        display aoambient 0.85
        display aodirect 0.35
        display backgroundgradient off
        color Display Background black
        axes location Off

        # VMD has no "salmon" among its 33 colours, so redefine ColorID 9 ("pink",
        # the nearest hue and rarely used elsewhere) to salmon #FA8072, then point
        # the Element category's carbon at it.  Element and Name are independent
        # categories, so the pocket (coloured by Name) keeps ordinary cyan carbons.
        #
        # NOTE: do NOT split the ligand into "and carbon" / "and not carbon" reps.
        # Licorice draws a bond only when BOTH atoms fall in the same rep, so every
        # C-N, C-O and C-H bond vanishes into the gap between them.
        color change rgb 9 0.98 0.50 0.45
        color Element C pink
        color Element H white
        color Name    C cyan
        color Name    H white

        # ---- polar hydrogens ---------------------------------------------------
        # A hydrogen is polar if it is bonded to N, O or S.  Bond lengths X-H are
        # ~1.0 A and the nearest non-bonded H...X contact is well beyond 1.3 A, so
        # a distance test is exact here.  Topology never changes, so evaluate it
        # ONCE and freeze the result as an index list -- a live "within" clause
        # would be recomputed every frame for an answer that cannot change.
        # It must run AFTER glue_traj: on split coordinates the distances are wrong.
        set scope "protein or ($ligsel)"
        set hsel [atomselect top "($scope) and hydrogen"]
        set psel [atomselect top "($scope) and hydrogen and within 1.3 of (($scope) and (nitrogen or oxygen or sulfur))" frame 0]
        set polarh [$psel get index]
        set nh [$hsel num]
        set np [llength $polarh]
        $psel delete
        $hsel delete
        if {$np == 0} {
            puts "vizard: WARNING -- no polar H found; showing heavy atoms only"
        }
        puts "vizard: showing $np polar H of $nh protein+ligand hydrogens"
        # heavy atoms plus polar H only; water is never in any of these reps
        set shown "(noh or index $polarh)"

        mol delrep 0 top

        mol representation NewCartoon 0.30 20.0 4.1 0
        mol selection "protein"
        mol color Structure
        mol material AOChalky
        mol addrep top
        set rep_cartoon [expr {[molinfo top get numreps] - 1}]

        # whole ligand in ONE rep -> all bonds drawn; carbons salmon via Element
        mol representation Licorice 0.15 30.0 30.0
        mol selection "($ligsel) and $shown"
        mol color Element
        mol material AOShiny
        mol addrep top
        set rep_ligand [expr {[molinfo top get numreps] - 1}]

        # pocket: whole residues within --pocket A of the ligand.  Distance-based, so it
        # must be re-evaluated every frame or it freezes at frame 0.
        mol representation Licorice 0.08 24.0 24.0
        mol selection "(same residue as (protein and within $pocketcut of ($ligsel))) and $shown"
        mol color Name
        mol material AOChalky
        mol addrep top
        set rep_pocket [expr {[molinfo top get numreps] - 1}]
        mol selupdate $rep_pocket top on
    }

    animate goto 0
    # frame as if only the ligand and pocket were shown, then bring the
    # cartoon back -- the framing you get from hiding the protein and
    # pressing "=" in the GUI
    # remember which reps define the framing, so a later display resize can
    # re-frame (changing the aspect ratio shifts what "fit" means)
    # only the single-molecule branch builds these; the multi-molecule branch
    # has already framed itself
    if {[info exists rep_ligand] && [info exists rep_pocket]} {
        set ::vizard_reps [list $rep_ligand $rep_pocket]
        glue_center -reps $::vizard_reps
    }
    # make vizard_movie available at the vmd> prompt
    puts "vizard: ready -- [molinfo top get numframes] frames,\
          view centred on '$ligsel'"
    if {[info commands vizard_movie] ne ""} {
        puts "vizard: type  vizard_movie -out movie.mp4   to render a video"
    }
}

if {[info exists argv] && ([lsearch -exact $argv "--help"] >= 0 ||
                           [lsearch -exact $argv "-h"] >= 0)} {
    vizard_help
    quit                      ;# --help came from the command line: nothing to show
}
if {[catch {vizard_main} vizard_err]} {
    puts "vizard: FAILED -- $vizard_err"
    puts "vizard: the trajectory shown is RAW and un-glued."
}
