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
trajectories after it attach to it.  Each molecule gets its own color and is
superposed onto the first:

  vizard a.pdb a.dcd b.pdb b.dcd 3ptb --ligand "resname LIG" --ref 1ubq

Options (all optional; values may contain spaces):

  --ligand SEL   ligand selection, used for reps, coloring, pocket and the
                 view center           (default "chain LIG L or resname LIG",
                 and if nothing is called that, the vizard_ligand macro:
                 what is left once protein, solvent, ions, lipid and sugar
                 are out -- the ligand of a fetched entry).  If that finds
                 nothing either, the protein alone is glued -- its chains
                 held together -- and shown.
  --glue SEL     what is held together across the periodic boundary
                                                  (default "protein or (<ligand>)")
  --align SEL    what the trajectory is fitted on
                 (default "(protein and name CA) or name BB GC" -- CA for an
                 all-atom model, BB for Martini, GC for SIRAH)
  --pocket A     pocket residue distance cutoff, angstroms      (default 6)
  --strip SEL    dropped right after loading, since it is never drawn and it
                 is most of the atoms         (default "water or ions";
                 "none" keeps everything).  Crystal structures are left be.
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

Selections are VMD syntax.  Some that work:

  --ligand "resname LIG"
  --ligand "chain B and not protein"
  --align  "protein and name CA and resid 145 to 149"
  --align  "protein and backbone and chain A"
  --glue   "protein or resname LIG or resname ZN"

Then, at the vmd> prompt:

  vizard_movie -out movie.mp4        render the trajectory to a video
  vizard_movie -h                    movie options
  browse                             step through the loaded molecules with
                                     the up/down arrows (bnext, bprev, off)
  ao off                             drop shadows + ambient occlusion, which
                                     are recomputed on every redraw (ao on
                                     puts them back; movies render with them)
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

Each fetched molecule gets its own color pair: a muted protein and a bright
ligand, so several structures stay distinguishable.
}
}

# More ligand molecules than this and it is co-solvent, not a ligand: it gets
# wrapped around the protein rather than held together with it.
set ::vizard_cosolvent 8

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
    foreach _f {movie formats align view browse cg} {
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
    # Values are VMD selection text, e.g. "protein and name CA and resid 1 to 40".
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
    set known {ligand lig glue align fit pocket out ref size fps step zoom keep reframe strip files}
    foreach k [lsort [array names A]] {
        if {[lsearch -exact $known $k] < 0} {
            error "unknown option '--$k'; known options are --[join [lsort $known] { --}]"
        }
    }

    set ligsel "chain LIG L or resname LIG"
    if {[info exists A(ligand)] && $A(ligand) ne ""} { set ligsel $A(ligand) }
    set gluesel "protein or ($ligsel)"
    if {[info exists A(glue)] && $A(glue) ne ""} { set gluesel $A(glue) }
    # CA for an all-atom model, BB for Martini, GC for SIRAH: a coarse-grained
    # model has no CA, and VMD's "protein" does not match its beads either, so
    # the residue name stands in for it -- otherwise a box of dipeptide probes
    # carrying a BB bead each joins the fit and the protein wanders.
    set cgpro [expr {[info commands ::CG::protein] ne "" ? [::CG::protein] : "none"}]
    set cgsolv [expr {[info exists ::CG::SOLVENT] ? [join $::CG::SOLVENT { }] : ""}]
    set alignsel "(protein and name CA) or (name BB GC and ($cgpro))"
    if {[info exists A(align)] && $A(align) ne ""} { set alignsel $A(align) }
    set stripsel "water or ions"
    if {[info exists A(strip)] && $A(strip) ne ""} { set stripsel $A(strip) }
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
    # ---- strip ------------------------------------------------------------
    # Waters, ions and the like are never drawn and are most of the atoms, so
    # dropping them makes the wrap step, the memory and every later redraw
    # smaller.  VMD cannot delete atoms from a molecule, so write what is kept
    # and load that back -- ~0.1 s for a 1000-frame box.  A crystal structure
    # is left alone: rewriting it would lose the spacegroup on its CRYST1 line,
    # which is what tells vizard not to treat its cell as a periodic box.
    if {[string tolower $stripsel] ni {none "" 0}} {
        set kept {}
        foreach m $mols {
            set keep ""
            # Neither "water" nor "ions" matches a Martini water bead, whose
            # residue is called W, so a coarse-grained model would keep every
            # one of them -- 5665 of 7266 beads in a pocket-search box.
            set ss $stripsel
            if {![info exists A(strip)] || $A(strip) eq ""} {
                if {[info commands ::CG::solvent] ne ""
                    && [::CG::coarse_grained $m]} {
                    set ss "($stripsel) or ([::CG::solvent])"
                }
            }
            if {[catch {atomselect $m "not ($ss)"} s]} {
                error "strip selection '$ss' is not valid VMD syntax: $s"
            }
            set nall [molinfo $m get numatoms]
            set ncut [expr {$nall - [$s num]}]
            if {$ncut == 0 || [$s num] == 0 || [::Glue::crystal_cell $m] ne ""} {
                $s delete ; lappend kept $m ; continue
            }
            set dir [::Glue::tempdir]
            set pdb [file join $dir solute.pdb]
            set nf [molinfo $m get numframes]
            $s writepdb $pdb
            if {$nf > 1} {
                set dcd [file join $dir solute.dcd]
                animate write dcd $dcd sel $s waitfor all $m
            }
            # A PDB carries no bonds, and VMD guesses them from distance when
            # it reads one back.  That is right for an all-atom model and
            # useless for a coarse-grained one, whose beads sit ~3.5 A apart:
            # every bead comes back unbonded, so making molecules whole has
            # nothing to walk and the wrap moves beads rather than molecules --
            # which splits a two-bead probe across the box.  So carry the
            # bonds over by hand, in the kept atoms' own numbering.
            set oldidx [$s list]
            set oldbonds [$s getbonds]
            $s delete
            mol delete $m
            set new [mol new $pdb waitfor all]
            if {$nf > 1} {
                mol addfile $dcd waitfor all $new
                animate delete beg 0 end 0 $new
            }
            unset -nocomplain map
            set i 0
            foreach o $oldidx { set map($o) $i ; incr i }
            set newbonds {}
            set clipped 0
            foreach bs $oldbonds {
                set row {}
                foreach b $bs {
                    if {[info exists map($b)]} { lappend row $map($b) }
                }
                # VMD stores at most 12 bonds per atom and refuses a longer
                # row.  A Martini elastic network goes past that, and VMD has
                # already dropped the extras itself while reading the file.
                if {[llength $row] > 12} {
                    incr clipped
                    set row [lrange $row 0 11]
                }
                lappend newbonds $row
            }
            set ns [atomselect $new all]
            if {[catch {$ns setbonds $newbonds} err]} {
                puts "vizard: could not carry the file's bonds across the strip\
                      ($err) -- VMD's distance guess stands, which a\
                      coarse-grained model will not survive"
            } else {
                # setbonds does not update the fragment numbering, which VMD
                # works out while reading a file -- and "pbc wrap -compound
                # fragment" is what the wrap moves molecules by, so without
                # this every bead is its own fragment and a molecule is torn
                # apart rather than moved.
                mol reanalyze $new
            }
            if {$clipped} {
                puts "vizard: $clipped atoms carry more than VMD's 12 bonds\
                      (an elastic network); the extras are dropped"
            }
            $ns delete
            lappend kept $new
            puts [format "vizard: molid %-3s dropped %d of %d atoms (%s);\
                  --strip none keeps them" $m $ncut $nall $ss]
        }
        set mols $kept
    }

    # A coarse-grained file names beads, not atoms: VMD leaves every one of
    # them element X, atomic number 0, and a radius picked off the first
    # letter -- 1.9 A for "SC1", which is sulfur's.  Give each bead the
    # element it stands for, so colouring by element means something.
    set cgmols {}
    if {[info commands vizard_cg_elements] ne ""} {
        foreach m $mols {
            if {[::CG::coarse_grained $m]} {
                lappend cgmols $m
                vizard_cg_elements $m
                vizard_cg_bonds $m
            }
        }
    }

    mol top [lindex $mols 0]

    # The default is a name, so it finds nothing in a structure whose ligand is
    # called something else -- ACO, BEN, BTN.  Fall back to whatever is left
    # once the protein, nucleic acids, solvent, ions, lipids and sugars are
    # taken away: that is the ligand in a fetched entry.  Peptide caps and the
    # usual crystallisation additives are not ligands and stay out of it.
    if {![info exists A(ligand)] || $A(ligand) eq ""} {
        set n 0
        foreach m $mols { set s [atomselect $m $ligsel]; incr n [$s num]; $s delete }
        if {$n == 0} {
            # as a macro, so it reads as one word in the output and can be
            # redefined: atomselect macro vizard_ligand "resname ACO"
            # ions covers the usual resnames (NA, CL, SOD, CLA, POT ...) and
            # the names catch an ion that arrived without one.  Caps are not
            # protein as far as VMD is concerned, and neither caps nor the
            # usual crystallisation additives are ligands.
            # the coarse-grained water and ion residues come from cg.tcl, so
            # the two lists cannot drift apart
            # $cgpro keeps a coarse-grained protein out: VMD's "protein"
            # matches none of its beads, so without it the protein itself
            # comes back as the ligand
            atomselect macro vizard_ligand "not (protein or nucleic or water or
                ions or lipid or glycan or ($cgpro)) and
                not name Na Cl NA CL and
                not resname ACE NME NMA NH2 GOL SO4 PO4 EDO PEG MPD ACT DMS\
                TRS $cgsolv"
            set alt "vizard_ligand"
            set n 0
            foreach m $mols {
                if {[catch {atomselect $m $alt} s]} { set n 0 ; break }
                incr n [$s num] ; $s delete
            }
            if {$n > 0} {
                puts "vizard: nothing called LIG -- taking the ligand as what is\
                      left once protein, solvent, ions, lipid and sugar are out"
                set ligsel $alt
                if {![info exists A(glue)] || $A(glue) eq ""} {
                    set gluesel "protein or ($ligsel)"
                }
            }
        }
    }

    foreach {label sel} [list ligand $ligsel glue $gluesel align $alignsel] {
        if {[catch {atomselect top "$sel"} s]} {
            error "$label selection '$sel' is not valid VMD syntax: $s"
        }
        set n [$s num] ; $s delete
        # No ligand is not an error: an apo protein, or a protein-protein
        # complex, is glued and viewed as protein alone.
        if {$n == 0 && $label eq "ligand"} {
            puts [format "vizard: %-6s %-44s %6d atoms -- none; protein only" \
                  $label "'$sel'" $n]
            continue
        }
        if {$n == 0} { error "$label selection '$sel' matched 0 atoms" }
        puts [format "vizard: %-6s %-44s %6d atoms" $label "'$sel'" $n]
    }
    set l [atomselect top "$ligsel"]
    set haslig [expr {[$l num] > 0}]
    $l delete

    # ---- glue + internal alignment, per molecule ---------------------------
    foreach m $mols {
        set nl [[atomselect $m "$ligsel"] num]
        set na [[atomselect $m "$alignsel"] num]
        if {$na < 3} {
            puts "vizard: molid $m -- align selection matches $na atoms, skipping"
            continue
        }
        # the default glue names the ligand; an explicit --glue is kept as given
        set g $gluesel
        set own [expr {[info exists A(glue)] && $A(glue) ne ""}]
        # VMD's "protein" matches none of a coarse-grained model, so the
        # protein's own beads are named by residue instead
        set pro [expr {[lsearch -exact $cgmols $m] >= 0 ? $cgpro : "protein"}]
        if {$nl == 0 && !$own} {
            set g $pro
            puts "vizard: molid $m -- no ligand matched; gluing protein only"
        } elseif {$nl > 0 && !$own} {
            # A ligand of a few molecules is held together with the protein
            # across the boundary.  A few hundred of them are not a ligand but
            # co-solvent -- the dipeptide probes of a pocket search, say -- and
            # holding those with the protein lets them outvote it over where
            # the cluster goes, so they come out on one side of the box in one
            # frame and the other side in the next.  Co-solvent is wrapped
            # around the protein instead, like water, which is what it is for.
            set ls [atomselect $m "$ligsel"]
            set nm [llength [lsort -unique -integer [$ls get fragment]]]
            $ls delete
            if {$nm > $::vizard_cosolvent} {
                set g $pro
                puts "vizard: molid $m -- $nm ligand molecules: co-solvent, not\
                      a ligand -- wrapped around the protein, not held with it"
            }
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
        set ::vizard_ref $refmol
        puts "vizard: reference '$A(ref)' loaded as molid $refmol"
    }

    # put every other molecule onto the first
    foreach m [lrange $mols 1 end] {
        if {[catch {vizard_matchmaker $m [lindex $mols 0] -sel $alignsel \
                                      -allframes 1} err]} {
            puts "vizard: WARNING -- could not superpose molid $m: $err"
        }
    }

    if {$haslig} {
        set p [atomselect top "protein" frame 0]
        set l [atomselect top "$ligsel" frame 0]
        set n [llength [lindex [measure contacts 5.0 $p $l] 0]]
        $p delete; $l delete
    }
    if {!$haslig} {
        puts "vizard: no ligand -- showing the protein"
    } elseif {$n == 0} {
        puts "vizard: WARNING -- no protein/ligand contacts within 5 A in"
        puts "vizard:            frame 0; is the ligand actually bound?"
    } else {
        puts "vizard: OK -- $n protein/ligand contacts within 5 A in frame 0"
    }

    if {[llength $mols] > 1} {
        # several systems: give each its own color scheme rather than the
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
        # reps 1 and 2 are ligand and pocket; without a ligand only the
        # cartoon, rep 0, exists
        set ::vizard_reps [expr {$haslig ? {1 2} : {0}}]
        catch { glue_center -molid [lindex $mols 0] -reps $::vizard_reps }
    } else {
        # Orthographic: no perspective foreshortening, so distances read true.
        display projection Orthographic

        # ---- display: matte ambient-occlusion look on white -------------------
        # Background is black, so depth cueing fogs toward black and distant atoms
        # darken -- the classic VMD look.  For a publication-style white figure,
        # set Background to white AND change Element/Name H to gray, or the
        # hydrogens vanish.  Everything below is cosmetic and safe to delete.
        # Depth cueing fogs toward the background color -- tune with
        # "display cuemode Linear|Exp|Exp2", cuedensity, cuestart, cueend.
        display projection Orthographic
        display rendermode GLSL
        display depthcue on
        display culling off
        display antialias on
        # Shadows and ambient occlusion are recomputed on every redraw, so on
        # a big enough system they cost something; "ao off" turns them off
        # when the pace matters more than the picture.
        display shadows on
        display ambientocclusion on
        display aoambient 0.85
        display aodirect 0.35
        display backgroundgradient off
        color Display Background black
        axes location Off

        # VMD has no "salmon" among its 33 colors, so redefine ColorID 9 ("pink",
        # the nearest hue and rarely used elsewhere) to salmon #FA8072, then point
        # the Element category's carbon at it.  Element and Name are independent
        # categories, so the pocket (colored by Name) keeps ordinary cyan carbons.
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
        # heavy atoms plus polar H only; water is never in any of these reps.
        # "index" with an empty list is a syntax error, and mol selection then
        # silently keeps the previous rep's text -- so a structure with no
        # polar H gets "noh", and one with no hydrogens at all needs no filter.
        if {$np > 0} {
            set shown "(noh or index $polarh)"
            puts "vizard: showing $np polar H of $nh protein+ligand hydrogens"
        } elseif {$nh > 0} {
            set shown "noh"
            puts "vizard: WARNING -- no polar H found; showing heavy atoms only"
        } else {
            set shown "all"
            puts "vizard: no hydrogens in the structure"
        }

        mol delrep 0 top

        # A coarse-grained model has no backbone for NewCartoon to follow --
        # VMD's own cartoon styles want atoms named CA -- so its backbone
        # beads, bonded to their neighbours above, are drawn as Licorice,
        # which comes out as the same continuous trace.
        set psel "protein"
        if {[lsearch -exact $cgmols [molinfo top]] >= 0} {
            # the protein's own backbone beads: every probe in a pocket-search
            # box carries a BB bead too, and 420 of those drawn as licorice
            # bury the trace this rep is for
            set psel "name BB GC and ($cgpro)"
            mol representation Licorice 0.60 20.0 20.0
            mol selection $psel
            mol color ColorID 10
        } else {
            mol representation NewCartoon 0.30 20.0 4.1 0
            mol selection "protein"
            mol color Structure
        }
        mol material AOChalky
        mol addrep top
        set rep_cartoon [expr {[molinfo top get numreps] - 1}]

        if {$haslig} {
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
            mol selection "(same residue as ($psel and within $pocketcut of ($ligsel))) and $shown"
            mol color Name
            mol material AOChalky
            mol addrep top
            set rep_pocket [expr {[molinfo top get numreps] - 1}]
            mol selupdate $rep_pocket top on
        }
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
    } elseif {[info exists rep_cartoon]} {
        set ::vizard_reps [list $rep_cartoon]
        glue_center -reps $::vizard_reps
    }
    # make vizard_movie available at the vmd> prompt
    puts "vizard: ready -- [molinfo top get numframes] frames,\
          view centered on [expr {$haslig ? "'$ligsel'" : "the protein"}]"
    if {[info commands vizard_movie] ne ""} {
        puts "vizard: type  vizard_movie -out movie.mp4   to render a video"
    }
    if {[info commands vizard_ao] ne ""} {
        puts "vizard: type  ao off  if redraws feel slow -- it drops the\
              shadows and ambient occlusion, which are recomputed on each one"
    }
    if {[llength $mols] > 1 && [info commands vizard_browse] ne ""} {
        puts "vizard: type  browse  to step through the [llength $mols]\
              molecules with the up/down arrows"
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
