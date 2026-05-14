// ============================================================
// PART 5: Lens Window Retainer Ring
// Holds the 50mm acrylic disc + O-ring over the scout camera
// aperture hole in the IP67 enclosure lid. Threaded or press-fit.
//
// Print: PETG, 100% infill, 0.15mm layer height
// Hardware: Acrylic disc (50mm x 3mm), O-ring (~45mm ID)
// Note: This part does NOT replace buying the acrylic disc,
//       but provides the frame to seat and seal it.
// ============================================================

// --- Parameters ---
window_dia      = 50;    // mm — acrylic disc diameter
window_thick    = 3;     // mm — acrylic disc thickness
oring_groove_d  = 45;    // mm — O-ring inner diameter
oring_cs        = 2;     // mm — O-ring cross-section diameter
ring_wall       = 4;     // mm — wall around window
ring_height     = 8;     // mm — total ring height
lip_height      = 1.5;   // mm — inner lip that holds disc from falling

ring_od = window_dia + ring_wall * 2;
ring_id = window_dia + 0.3;  // slight clearance for disc

$fn = 80;

module retainer_ring() {
    difference() {
        // Outer ring body
        cylinder(h = ring_height, d = ring_od);
        
        // Window bore (disc sits here)
        translate([0, 0, lip_height])
            cylinder(h = ring_height, d = ring_id);
        
        // Viewing aperture through the lip
        translate([0, 0, -1])
            cylinder(h = lip_height + 2, d = window_dia - 6);
        
        // O-ring groove (cut into the bore wall at disc seating level)
        translate([0, 0, lip_height + 0.5])
            difference() {
                cylinder(h = oring_cs + 0.5, d = ring_id + oring_cs);
                translate([0, 0, -0.1])
                    cylinder(h = oring_cs + 0.7, d = ring_id - 0.2);
            }
    }
}

retainer_ring();
