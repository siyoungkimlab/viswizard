############################################################
# align.tcl -- fetch structures from the PDB, and superpose them by
# SEQUENCE so residue numbering does not have to match.
#
#   vizard_fetch 1ubq
#   vizard_matchmaker 1 0                 ;# move molid 1 onto molid 0
#   vizard_matchmaker 1 0 -sel "protein and name CA" -cutoff 2.0
#
# vizard_matchmaker aligns the two sequences (Needleman-Wunsch), fits the
# matched CA pairs, then re-fits while dropping pairs further apart than
# -cutoff -- the same idea as ChimeraX matchmaker / PyMOL cealign.  VMD's own
# "measure fit" needs equal atom counts in matching order, which is exactly
# what fails when numbering differs.
############################################################

if {[info exists ::vizard_align_loaded]} { return }
set ::vizard_align_loaded 1

proc vizard_cache {} {
    set d [file join $::env(HOME) .viswizard_cache]
    if {![file isdirectory $d]} { file mkdir $d }
    return $d
}

proc vizard_fetch {code args} {
    set code [string toupper $code]
    set type pdb
    if {[lsearch -exact $args "-cif"] >= 0} { set type cif }
    set ext [expr {$type eq "cif" ? "cif" : "pdb"}]
    set f [file join [vizard_cache] "$code.$ext"]
    if {![file exists $f] || [file size $f] == 0} {
        set url "https://files.rcsb.org/download/$code.$ext"
        set curl [lindex [auto_execok curl] 0]
        if {$curl eq ""} { error "vizard_fetch: curl not found" }
        if {[catch {exec $curl -sfL --max-time 60 $url -o $f} e]} {
            catch {file delete $f}
            error "vizard_fetch: could not download $code ($e)"
        }
        puts "vizard_fetch: downloaded $code -> $f"
    } else {
        puts "vizard_fetch: using cached $f"
    }
    set molid [mol new $f type [expr {$ext eq "cif" ? "pdbx" : "pdb"}] waitfor all]
    puts "vizard_fetch: $code is molid $molid ([molinfo $molid get numatoms] atoms)"
    if {[lsearch -exact $args "-noreps"] < 0} {
        set ra {}
        set i [lsearch -exact $args "-ligand"]
        if {$i >= 0} { set ra [list -ligand [lindex $args $i+1]] }
        set i [lsearch -exact $args "-pocket"]
        if {$i >= 0} { lappend ra -pocket [lindex $args $i+1] }
        catch { eval vizard_reps $molid $ra }
        display projection Orthographic
        display depthcue on
        color Display Background black
        axes location Off
    }
    return $molid
}

proc vizard_matchmaker {mob ref args} {
    array set opt {-sel "protein and name CA" -cutoff 2.0 -iterations 5 \
                   -apply all -allframes 0}
    array set opt $args
    if {$mob eq "top"} { set mob [molinfo top] }
    if {$ref eq "top"} { set ref [molinfo top] }

    set py [vizard_python]
    set here [file dirname [file normalize [info script]]]
    set script [file join $here .. pizard superpose.py]
    if {![file exists $script]} {
        set script [file join $::env(HOME) viswizard pizard superpose.py]
    }
    if {![file exists $script]} { error "vizard_matchmaker: superpose.py not found" }

    set a [atomselect $mob $opt(-sel)]
    set b [atomselect $ref $opt(-sel)]
    if {[$a num] < 3 || [$b num] < 3} {
        $a delete ; $b delete
        error "vizard_matchmaker: need at least 3 CA atoms in each ('$opt(-sel)')"
    }
    set dump [file join [vizard_cache] "mm_[pid].txt"]
    set fh [open $dump w]
    foreach tag {A B} sel [list $a $b] {
        foreach rn [$sel get resname] xyz [$sel get {x y z}] {
            lassign $xyz x y z
            puts $fh "$tag\t$rn\t$x\t$y\t$z"
        }
    }
    close $fh
    set na [$a num] ; set nb [$b num]
    $a delete ; $b delete

    set out [exec $py $script $dump $opt(-cutoff) $opt(-iterations)]
    file delete $dump
    set M {} ; set stats {}
    foreach line [split $out \n] {
        if {[string match "MATRIX *" $line]} { set M [lrange $line 1 end] }
        if {[string match "STATS *" $line]}  { set stats [lrange $line 1 end] }
    }
    if {[llength $M] != 16} { error "vizard_matchmaker: bad matrix from superpose.py:\n$out" }
    set mat [list [lrange $M 0 3] [lrange $M 4 7] [lrange $M 8 11] [lrange $M 12 15]]

    # "$sel move" transforms the CURRENT frame only, so a trajectory has to be
    # walked frame by frame.
    set s [atomselect $mob $opt(-apply)]
    if {$opt(-allframes)} {
        set keep [molinfo $mob get frame]
        for {set n 0} {$n < [molinfo $mob get numframes]} {incr n} {
            $s frame $n
            $s move $mat
        }
        molinfo $mob set frame $keep
    } else {
        $s move $mat
    }
    $s delete
    lassign $stats n0 nk rms
    puts [format "vizard_matchmaker: %d vs %d CA -> %s aligned, %s kept, rmsd %s A" \
          $na $nb $n0 $nk $rms]
    # A structural superposition of unrelated proteins still "succeeds"; the
    # give-aways are a low match count and a high rmsd, so say so out loud.
    set frac [expr {double($n0) / [expr {$na < $nb ? $na : $nb}]}]
    if {$rms > 5.0 || $frac < 0.5} {
        puts [format "vizard_matchmaker: WARNING -- only %.0f%% of the shorter\
              chain matched and rmsd is %.1f A; are these the same protein?" \
              [expr {100*$frac}] $rms]
    }
    return $rms
}

############################################################
# vizard_reps -- the standard vizard look, applied to one molecule.
#
#   vizard_reps 0
#   vizard_reps 1 -ligand "resname BEN" -pocket 5
#
# Each molid gets its own carbon colour so several structures stay
# distinguishable.  VMD's Element/Name colour categories are global, so a
# per-molecule carbon colour cannot come from them: instead the whole
# molecule is drawn in its ColorID and the heteroatoms are overlaid as
# slightly fatter spheres coloured by element.  Drawing the ligand as one
# rep (rather than splitting carbon/non-carbon) keeps every bond drawn.
############################################################

# Paired palettes, one pair per molecule: a muted protein and a bright
# ligand-carbon colour of the same hue.
#
# VMD's stock 33 colours are saturated and unpleasant for carbons, so these
# are redefined to a soft, figure-friendly set.  Only ColorIDs 17-32 are
# touched -- the "2"/"3" variants nothing uses by default.  IDs 0-16 carry the
# Element, Name and Structure category colours (C=cyan, N=blue, O=red,
# S=yellow, helix=purple ...) and are left alone, so heteroatoms and
# secondary-structure colouring are unaffected.
#
# Side effect: the GUI colour menu still calls ID 18 "yellow3" etc. while it
# now renders salmon.  Nothing reads those names.

proc vizard_define_colors {} {
    if {[info exists ::vizard_colors_defined]} { return }
    set ::vizard_colors_defined 1
    # PyMOL's palette, ported so both tools look the same.  The eight pairs
    # were chosen by searching for the maximum minimum separation between
    # schemes -- cartoons AND ligand carbons -- then ordered so consecutive
    # molecules are as far apart as possible.  Odd ids = cartoon/pocket,
    # even ids = ligand carbons.
    #        cartoon               ligand
    foreach {id r g b} {
        17 0.200 0.600 0.200    18 0.651 0.902 0.651
        19 0.698 0.302 0.400    20 1.000 0.749 0.871
        21 0.769 0.702 0.000    22 1.000 1.000 0.502
        23 0.251 0.251 0.651    24 0.749 0.749 1.000
        25 0.698 0.129 0.129    26 1.000 0.600 0.600
        27 0.102 0.600 0.600    28 0.800 1.000 1.000
        29 0.600 0.102 0.600    30 1.000 0.502 1.000
        31 0.651 0.322 0.169    32 0.988 0.820 0.651
    } {
        color change rgb $id $r $g $b
    }
    color change rgb 9 0.98 0.50 0.45
}

proc vizard_palette {} {
    vizard_define_colors
    # {protein ligand} pairs: grey/salmon, slate/palecyan, sage/palegreen,
    # mauve/violet, tan/wheat, steel/lightblue, clay/lightorange,
    # moss/paleyellow.  (Comments must stay OUT of the braced list: inside
    # braces ";#" is literal text, not a comment, and lands in the list.)
    return {{17 18} {19 20} {21 22} {23 24} {25 26} {27 28} {29 30} {31 32}}
}

proc vizard_reps {molid args} {
    array set opt {-ligand "" -pocket 5.0 -color -1 -proteincolor -1 -polaronly 1}
    array set opt $args
    if {$molid eq "top"} { set molid [molinfo top] }

    set pal [vizard_palette]
    # assign schemes in the order molecules are set up, so deleting and
    # reloading does not make the colours jump around with the molid
    if {![info exists ::vizard_scheme($molid)]} {
        if {![info exists ::vizard_scheme_next]} { set ::vizard_scheme_next 0 }
        set ::vizard_scheme($molid) $::vizard_scheme_next
        incr ::vizard_scheme_next
    }
    set scheme [expr {$::vizard_scheme($molid) % [llength $pal]}]
    lassign [lindex $pal $scheme] pc lc
    if {$opt(-color) >= 0} { set lc $opt(-color) }
    if {$opt(-proteincolor) >= 0} { set pc $opt(-proteincolor) }

    set lig $opt(-ligand)
    if {$lig eq ""} { set lig "not (protein or nucleic or water or ions)" }
    set ls [atomselect $molid $lig]
    set nlig [$ls num]
    $ls delete

    # heavy atoms plus polar H (bonded to N/O/S); computed once, topology fixed
    set shown "all"
    if {$opt(-polaronly)} {
        set ps [atomselect $molid \
            "hydrogen and within 1.3 of (nitrogen or oxygen or sulfur)"]
        set idx [$ps get index]
        $ps delete
        # "index" with an empty list is a syntax error, and mol selection then
        # silently keeps the previous rep's text.  A structure with no
        # hydrogens at all needs no filtering anyway.
        if {[llength $idx] > 0} {
            set shown "(noh or index $idx)"
        } elseif {[[atomselect $molid hydrogen] num] > 0} {
            set shown "noh"
        }
    }

    while {[molinfo $molid get numreps] > 0} { mol delrep 0 $molid }

    mol representation NewCartoon 0.30 20.0 4.1 0
    mol selection "protein"
    mol color ColorID $pc
    mol material AOChalky
    mol addrep $molid

    if {$nlig > 0} {
        # Element, Name and Type are three INDEPENDENT global colour
        # categories that all default to the same element colours.  Giving
        # each molecule its own category lets its carbons be recoloured
        # without touching the others -- one rep, real element colours for
        # N/O/S, and no second rep drawn on top of the first.
        set cats {Element Name Type}
        if {$scheme < [llength $cats]} {
            set cat [lindex $cats $scheme]
            color $cat C [lindex [colorinfo colors] $lc]
            set ligcolor [list $cat]
        } else {
            # out of categories: solid colour, heteroatoms lose element colours
            set ligcolor [list ColorID $lc]
        }
        mol representation Licorice 0.15 30.0 30.0
        mol selection "($lig) and $shown"
        eval mol color $ligcolor
        mol material AOShiny
        mol addrep $molid

        mol representation Licorice 0.08 24.0 24.0
        mol selection \
            "(same residue as (protein and within $opt(-pocket) of ($lig))) and $shown"
        mol color ColorID $pc
        mol material AOChalky
        mol addrep $molid
        mol selupdate [expr {[molinfo $molid get numreps] - 1}] $molid on
    }

    # frame on ligand + pocket if there is a ligand, else on everything
    if {$nlig > 0 && [info commands glue_center] ne ""} {
        catch { glue_center -molid $molid -reps {1 2} }
    }
    puts [format "vizard_reps: molid %s scheme %d (dark/bright %s), %d ligand atoms" \
          $molid $scheme [lindex [vizard_palette_names] $scheme] $nlig]
    return [list $pc $lc]
}


# short aliases, for typing
interp alias {} matchmaker {} vizard_matchmaker
interp alias {} mm         {} vizard_matchmaker
interp alias {} fetch      {} vizard_fetch
interp alias {} reps       {} vizard_reps

proc vizard_palette_names {} {
    return {green raspberry olive blue red teal purple brown}
}
