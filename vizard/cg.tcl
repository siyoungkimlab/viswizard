############################################################
# cg.tcl -- what element a coarse-grained bead stands for.
#
#   cgelem            give every bead the element it stands for
#   cgelem 1          the same, for molid 1
#
# A Martini or SIRAH file names beads, not atoms, and says nothing about
# elements, so VMD gives every bead element X, atomic number 0 and a radius
# picked off the first letter -- 1.9 A for "SC1", which is sulfur's.  Wrong
# elements mean wrong colours and wrong radii.
#
# The tables are the ones in pizard/cg.py; tests/test_cg.py checks that the
# two agree.  Keep them in step.
############################################################
if {[info exists ::vizard_cg_loaded]} { return }
set ::vizard_cg_loaded 1

namespace eval ::CG:: {}

# ion beads, which VMD would otherwise leave as element X
array set ::CG::IONS {NA Na SOD Na CL Cl CLA Cl K K POT K CA Ca CAL Ca MG Mg ZN Zn CES Cs CS Cs NAW Na CLW Cl}
# Martini beads whose name says nothing about the element
array set ::CG::EXACT {BB C PO4 P NC3 N CNO N}
# prefix -> element, first match winning
set ::CG::PREFIX {SC C GL C W O C C D C}
# SIRAH names a bead for the atom it is centred on: the second letter
set ::CG::SIRAH_FIRST BG
set ::CG::SIRAH_ELEMENTS CNOSP
# any of these means the model is coarse-grained
set ::CG::MARKERS {BB GC GN SC1}
# the residues whose beads are protein.  VMD's "protein" wants a full
# N/CA/C/O backbone and matches none of a coarse-grained model, so the residue
# name is what is left to go on -- and it is what tells the protein's own beads
# from a box of dipeptide probes (WW, FY, EE), whose names no viewer knows.
set ::CG::RESIDUES {ALA ARG ASN ASP CYS GLN GLU GLY HIS ILE LEU LYS MET PHE
    PRO SER THR TRP TYR VAL HID HIE HIP HISD HISE HISH CYX CYM ACE NME NMA}
# SIRAH names its residues for itself -- sL, sK, sHe -- so a SIRAH protein
# matches none of the above.  Their case is their own: upper-cased, sS, sT, sW
# and sY are the dipeptide probes SS, ST, SW and SY, and a box of probes would
# come out as protein.
set ::CG::SIRAH_RESIDUES {sA sC sCp sD sDh sE sEh sF sG sHd sHe sI sK sKa sKm
    sL sM sN sP sQ sR sS sSp sT sTp sV sW sX sY sYp sZ}
# atomic numbers, so the element and the number never disagree
array set ::CG::Z {H 1 C 6 N 7 O 8 Na 11 Mg 12 P 15 S 16 Cl 17 K 19 Ca 20 Zn 30 Cs 55}

proc ::CG::element {name} {
    variable IONS
    variable EXACT
    variable PREFIX
    variable SIRAH_FIRST
    variable SIRAH_ELEMENTS
    set n [string toupper [string trim $name]]
    if {$n eq ""} { return "" }
    if {[info exists IONS($n)]} { return $IONS($n) }
    if {[info exists EXACT($n)]} { return $EXACT($n) }
    if {[string length $n] >= 2
        && [string first [string index $n 0] $SIRAH_FIRST] >= 0
        && [string first [string index $n 1] $SIRAH_ELEMENTS] >= 0} {
        return [string index $n 1]
    }
    foreach {prefix elem} $PREFIX {
        if {[string first $prefix $n] == 0} { return $elem }
    }
    return ""
}

# the residue names coarse-grained solvent and ions come under: VMD's "water"
# matches none of them, so without this a Martini box strips almost nothing
# VMD matches a resname with its case, so SIRAH's NaW and ClW are listed as
# SIRAH writes them as well as upper-cased
set ::CG::SOLVENT {W WF WN WT4 ION NA CL SOD CLA POT CAL MG ZN NAW CLW NaW ClW}

proc ::CG::solvent {} {
    variable SOLVENT
    return "resname [join $SOLVENT { }]"
}

# A selection for the protein's own beads: the analogue of PyMOL's polymer
# flag, which pizard's readers set from the same list.
proc ::CG::protein {} {
    variable RESIDUES
    variable SIRAH_RESIDUES
    return "resname [join [concat $RESIDUES $SIRAH_RESIDUES] { }]"
}

proc ::CG::coarse_grained {molid} {
    variable MARKERS
    set s [atomselect $molid all]
    set names [lsort -unique [$s get name]]
    $s delete
    foreach m $MARKERS {
        if {[lsearch -exact $names $m] >= 0} { return 1 }
    }
    return 0
}

# A bead is several atoms' worth of one, so it keeps the radius VMD gave it --
# only the element and its number are wrong, and those are what colouring and
# the Element category read.
proc vizard_cg_elements {{molid top} {quiet 0}} {
    variable ::CG::Z
    if {$molid eq "top"} { set molid [molinfo top] }
    set all [atomselect $molid all]
    set names [lsort -unique [$all get name]]
    $all delete
    set done 0
    foreach nm $names {
        set el [::CG::element $nm]
        if {$el eq ""} continue
        set s [atomselect $molid "name $nm"]
        $s set element $el
        if {[info exists ::CG::Z($el)]} { $s set atomicnumber $::CG::Z($el) }
        incr done [$s num]
        $s delete
    }
    if {!$quiet} {
        puts "cgelem: molid $molid -- gave $done beads the element they stand for"
    }
    return $done
}

# A coarse-grained file carries no bonds -- its beads sit ~3.5 A apart, past
# any distance-based bond search -- so VMD draws them as loose dots and its
# cartoon styles have nothing to follow.  Tube, Trace and Ribbons are no help
# either: they follow atoms named CA, and renaming a bead would break every
# selection that looks for it.  Bonding each backbone bead to the next one in
# its chain and drawing Licorice gives the same continuous backbone.
proc vizard_cg_bonds {{molid top} {quiet 0} {cutoff 6.0}} {
    if {$molid eq "top"} { set molid [molinfo top] }
    # the protein's own backbone beads.  Bonding "name BB GC" wholesale walks
    # the list in file order, so in a box of dipeptide probes -- each carrying
    # one BB bead, all under the same chain and segname -- it bonds beads of
    # different molecules that happen to be within the cutoff.  Those bonds
    # then stretch across the box the moment anything is wrapped.
    set bb [atomselect $molid "name BB GC and ([::CG::protein])"]
    set nbb [$bb num]
    if {$nbb < 2} { $bb delete ; return 0 }
    set all [atomselect $molid all]
    set bonds [$all getbonds]
    set idx [$bb list]
    set ch [$bb get chain]
    set sg [$bb get segname]
    set crd [$bb get {x y z}]
    set added 0
    set already 0
    set full 0
    set c2 [expr {$cutoff * $cutoff}]
    for {set i 0} {$i < [llength $idx] - 1} {incr i} {
        set j [expr {$i + 1}]
        # One chain only, so two chains that happen to touch stay apart.
        if {[lindex $ch $i] ne [lindex $ch $j]} continue
        if {[lindex $sg $i] ne [lindex $sg $j]} continue
        # Neighbours by distance, not by residue number: a renumbered or
        # gapped chain would get no bonds at all from "resid + 1", and
        # isolated beads look exactly like nothing being drawn.  A break in
        # the chain is far further apart than the ~3.5 A between beads.
        lassign [lindex $crd $i] xi yi zi
        lassign [lindex $crd $j] xj yj zj
        set dx [expr {$xj-$xi}] ; set dy [expr {$yj-$yi}] ; set dz [expr {$zj-$zi}]
        if {$dx*$dx + $dy*$dy + $dz*$dz > $c2} continue
        set a [lindex $idx $i]
        set b [lindex $idx $j]
        # a .mae or .dms carries the model's own bonds, so there is often
        # nothing to add -- say so rather than reporting a bare zero
        if {[lsearch -exact [lindex $bonds $a] $b] >= 0} { incr already ; continue }
        # VMD stores at most 12 bonds per atom and refuses a longer row.  A
        # Martini elastic network already fills that, and a bead with twelve
        # bonds is drawn connected to its neighbours anyway.
        if {[llength [lindex $bonds $a]] >= 12 || [llength [lindex $bonds $b]] >= 12} {
            incr full
            continue
        }
        lset bonds $a [concat [lindex $bonds $a] $b]
        lset bonds $b [concat [lindex $bonds $b] $a]
        incr added
    }
    if {[catch {$all setbonds $bonds} err]} {
        $all delete ; $bb delete
        if {!$quiet} { puts "cgbonds: molid $molid -- could not bond the\
                             backbone beads ($err)" }
        return 0
    }
    $all delete ; $bb delete
    # setbonds leaves the fragment numbering as VMD worked it out while
    # reading the file, and that is what wrapping moves molecules by
    if {$added} { mol reanalyze $molid }
    if {!$quiet} {
        if {$added == 0 && ($already > 0 || $full > 0)} {
            puts "cgbonds: molid $molid -- the file already bonds its $nbb\
                  backbone beads; nothing to add"
        } else {
            puts "cgbonds: molid $molid -- bonded $added of $nbb backbone beads\
                  to the next (within $cutoff A)"
        }
    }
    return $added
}

interp alias {} cgelem  {} vizard_cg_elements
interp alias {} cgbonds {} vizard_cg_bonds
