// ============================================================
// PART 1: Gimbal Nozzle Bracket
// Mounts Orbit 66190 nozzle alongside IMX219 camera on
// Storm32 gimbal payload plate.
//
// Print: PETG or ABS, 100% infill, 0.2mm layer height
// Hardware: 2x M2.5 screws (shared with camera mount holes)
// Replaces: "3D-Printed Nozzle Bracket" in moreparts.csv ($5)
// ============================================================

// --- Parameters (adjust to your hardware) ---
plate_width      = 40;    // mm — matches Storm32 payload plate
plate_depth      = 55;    // mm
plate_thickness  = 3;     // mm — base plate
nozzle_bore      = 11;    // mm — bore for Orbit 66190 10-32 thread
nozzle_holder_h  = 15;    // mm — height of nozzle holder tube
nozzle_holder_od = 16;    // mm — outer diameter of holder tube
nozzle_offset_x  = 14;    // mm — offset from center (beside camera)

// Mounting holes for Storm32 payload plate (4x M2.5)
mount_hole_dia   = 2.8;   // mm — clearance for M2.5
mount_spacing_x  = 30;    // mm — center-to-center
mount_spacing_y  = 30;    // mm — center-to-center

// Camera cutout (so camera lens is not blocked)
cam_cutout_dia   = 20;    // mm — lens + housing clearance

$fn = 60;

module nozzle_bracket() {
    difference() {
        union() {
            // Base plate
            translate([-plate_width/2, -plate_depth/2, 0])
                cube([plate_width, plate_depth, plate_thickness]);
            
            // Nozzle holder tube
            translate([nozzle_offset_x, 12, 0])
                cylinder(h = nozzle_holder_h, d = nozzle_holder_od);
        }
        
        // Nozzle bore (through the holder tube)
        translate([nozzle_offset_x, 12, -1])
            cylinder(h = nozzle_holder_h + 2, d = nozzle_bore);
        
        // Camera lens clearance hole
        translate([-nozzle_offset_x + 4, 0, -1])
            cylinder(h = plate_thickness + 2, d = cam_cutout_dia);
        
        // 4x M2.5 mounting holes
        for (x = [-mount_spacing_x/2, mount_spacing_x/2])
            for (y = [-mount_spacing_y/2, mount_spacing_y/2])
                translate([x, y, -1])
                    cylinder(h = plate_thickness + 2, d = mount_hole_dia);
    }
}

nozzle_bracket();
