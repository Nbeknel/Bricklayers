# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# Copyright (c) [2025] [Roman Tenger]
from pickle import FALSE
import re
import sys
import logging
import os
import argparse
import math

# Get the directory where the script is located
script_dir = os.path.dirname(os.path.abspath(__file__))

# Configure logging to save in the script's directory
log_file_path = os.path.join(script_dir, "z_shift_log.txt")
logging.basicConfig(
    filename=log_file_path,
    filemode="w",
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

class LineSegment:
    def __init__(self, x0, y0, x1, y1):
        self.x0 = x0
        self.y0 = y0
        self.x1 = x1
        self.y1 = y1

    def distance(self, x0, y0, x1, y1):
        # 2 line segments from perimeters should not intersect each other, if they do, then something is wrong on the slicers side.

        dx0 = self.x1 - self.x0
        dy0 = self.y1 - self.y0

        dx1 = x1 - x0
        dy1 = y1 - y0

        delta = dx0 * dy1 - dx1 * dy0

        # find projections onto first line segment
        r0 = math.sqrt(dx0 ** 2 + dy0 ** 2)

        dx = x0 - self.x0
        dy = y0 - self.y0
        a1 = (dx0 * dx + dy0 * dy) / r0

        dx = x1 - self.x0
        dy = y1 - self.y0
        a2 = (dx0 * dx + dy0 * dy) / r0

        # if projections are on the line segment, find the distances between line and points, return minimum
        if 0 <= a1 <= 1 and 0 <= a2 <= 1:
            l1 = abs(dy0 * (x0 - self.x0) - dx0 * (y0 - self.y0)) / r0
            l2 = abs(dy0 * (x1 - self.x0) - dx0 * (y1 - self.y0)) / r0
            return min(l1, l2)

        # find projections onto second line segment
        r1 = math.sqrt(dx1 ** 2 + dy1 ** 2)

        dx = self.x0 - x0
        dy = self.y0 - y0
        a1 = (dx1 * dx + dy1 * dy) / r1
        
        dx = self.x1 - x0
        dy = self.y1 - y0
        a2 = (dx1 * dx + dy1 * dy) / r1

        # if projections are on the line segment, find the distances between line and points, return minimum
        if 0 <= a1 <= 1 and 0 <= a2 <= 1:
            l1 = abs(dy1 * (self.x0 - x0) - dx1 * (self.y0 - y0)) / r1
            l2 = abs(dy1 * (self.x1 - x0) - dx1 * (self.y1 - y0)) / r1
            return min(l1, l2)

        # if both line segments are nearly parallel, calculate the distance between line and point
        if abs(delta) < 1e-5:
            return abs(dy0 * (x0 - self.x0) - dx0 * (y0 - self.y0)) / r0

        # find al distances between two endpoints of different line segments and return their minimum
        l1 = math.sqrt((x0 - self.x0) ** 2 + (y0 - self.y0) ** 2)
        l2 = math.sqrt((x1 - self.x0) ** 2 + (y1 - self.y0) ** 2)
        l3 = math.sqrt((x0 - self.x1) ** 2 + (y0 - self.y1) ** 2)
        l4 = math.sqrt((x1 - self.x1) ** 2 + (y1 - self.y1) ** 2)
        
        return min(l1, l2, l3, l4)



class Object:
        def __init__(self, nozzle_diameter, x=0, y=0):
            self.layer_num = -1
            self.has_top = [False]
            self.has_overhangs = [False]
            self.external_perimeters = []
            self.nozzle_diameter = nozzle_diameter
            self.x = x
            self.y = y
            self.layer_height = []
            self.layer_z = []
            self.perimeter_width = nozzle_diameter * 1.125
            self.perimeter_width_sum = 0
            self.perimeter_length = 0
            self.average_perimeter_width = []

        def update_coordinates(self, x, y):
            self.x = x
            self.y = y

        def update_perimeter_width(self, perimeter_width):
            self.perimeter_width = perimeter_width

        def new_layer(self, x, y):
            self.has_top.append(False)
            self.has_overhangs.append(False)
            self.external_perimeters.append([])
            self.update_coordinates(x, y)
            self.average_perimeter_width.append(self.perimeter_width_sum / self.perimeter_length)

        def add_external_perimeter_line(self, x, y):
            self.external_perimeters.append(LineSegment(self.x, self.y, x, y))
            self.update_coordinates(x, y)

        def add_internal_perimeter_line(self, x, y):
            l = math.sqrt((self.x - x) ** 2 + (self.y - y) ** 2)
            self.perimeter_width_sum += self.perimeter_width * l
            self.perimeter_length += l


def process_gcode(input_file, layer_height, extrusion_multiplier):
    # Lists per perimeter type
    external_perimeter = ["External perimeter", "Outer wall"]
    internal_perimeter = ["Perimeter", "Inner wall", "Internal perimeter"]
    overhang_perimeter = ["Overhang perimeter"]
    top_solid = ["Top solid infill"]

    # Basically a C enum for extrusion types
    EXTERNAL_PERIMETER = 0
    INTERNAL_PERIMETER = 1
    OVERHANG_PERIMETER = 2
    OTHER = -1

    layer_num = 0
    layer_z = 0.0
    perimeter_type = OTHER
    z_shift = layer_height * 0.5
    logging.info("Starting G-code processing")
    logging.info(f"Input file: {input_file}")
    logging.info(f"Z-shift: {z_shift} mm, Layer height: {layer_height} mm")

    objects = {}
    current_object = ""
    current_x = 0
    current_y = 0
    previous_x = 0
    previous_y = 0
    perimeter_spacing = 0.4
    perimeter_contour = []

    # Read the input G-code
    with open(input_file, 'r') as infile:
        lines = infile.readlines()

    # Preprocess
    for line in lines:
        # Get perimeter type
        match = re.search(r";TYPE:([^n]*)", line)
        if match:
            if match.group(1) in external_perimeter:
                perimeter_type = EXTERNAL_PERIMETER
            elif match.group(1) in  internal_perimeter:
                perimeter_type = INTERNAL_PERIMETER
            elif match.group(1) in top_solid:
                objects[current_object].has_top[-1] = True
            elif match.group(1) in overhang_perimeter:
                objects[current_object].has_overhang[-1] = True
            else:
                perimeter_type = OTHER

        # Get line width from comments
        match = re.search(r";WIDTH:([\.\d]+)", line)
        if match:
            objects[current_object].update_perimeter_width(float(match.group(1)))

        # Get X coordinate from G1 move
        match = re.search(r"G1 [^X\n]*X([-\d\.]+)", line)
        if match:
            current_x = float(match.group(1))

        # Get Y coordinate from G1 move
        match = re.search(r"G1 [^Y\n]*Y([-\d\.]+)", line)
        if match:
            current_y = float(match.group(1))

        # Get Z values
        match = re.search(r";Z:([\.\d]+)", line)
        if match:
            objects[current_object].layer_z.append(float(match.group(1)))
        match = re.search(r";HEIGHT:([\.\d]+)", line)
        if match:
            objects[current_object].layer_height.append(float(match.group(1)))

        # Add a line segment if an external perimeter is being extruded
        match = re.search(r"G1 ([^XY]*(X|Y))+[^E]*E[^-]", line)
        if match:
            if perimeter_type == EXTERNAL_PERIMETER:
                objects[current_object].add_external_perimeter_line(current_x, current_y)

        # Find the boundary of an object, all data is stored per object
        match = re.search(r";printing object ([^\n]*)", line)
        if match:
            current_object = match.group(1)
            if current_object in objects.keys:
                objects[current_object].new_layer(current_x, current_y)
            else:
                objects[current_object] = Object(current_x, current_y)

    # Process the G-code
    modified_lines = []
    for line in lines:
        # Detect current object
        # Currently supports only OctoPrint comments
        match = re.search(r";printing object ([^\n]*)", line)
        if match:
            current_object = match.group(1)
            objects[current_object].layer_num += 1
            layer_num = objects[current_object].layer_num
            layer_z = objects[current_object].layer_z[layer_num]
            logging.info(f"Layer {layer_num} detected at Z={layer_z:.3f}")
            modified_lines.append(line)
            perimeter_contour = []
            inside_perimeter_contour = False
            continue

        # Store X and Y-positions in memory
        if 'X' in line or 'Y' in line:
            match = re.search(r"X([-\d\.])+", line)
            if match:
                previous_x, current_x = current_x, float(match.group(1))

            match = re.search(r"Y([-\d\.])+", line)
            if match:
                previous_y, current_y = current_y, float(match.group(1))

        # Skip layers that have top solid infill or overhang perimeters, and the first layer
        # Perimeters around top solid infill should be flush with the top surface
        # Overhang perimeters are hard to work with, maybe in a later update
        # This scripts shifts the affected perimeters downwards, therefore, lowering the layer height on the first layer might be problematic
        if objects[current_object].has_overhangs[layer_num] or objects[current_object].has_top[layer_num] or layer_num == 0:
            modified_lines.append(line)
            continue

        # Detect perimeter types from G-code comments
        match = re.search(r";TYPE:([^n]*)", line)
        if match:
            if match.group(1) in external_perimeter:
                perimeter_type = EXTERNAL_PERIMETER
                logging.info(f"External perimeter detected at layer {layer_num}")
                modified_lines.append(f"G1 Z{layer_z:.3f}\n")
            elif match.group(1) in  internal_perimeter:
                perimeter_type = INTERNAL_PERIMETER
                logging.info(f"Internal perimeter contour started at layer {layer_num}")
            else:
                perimeter_type = OTHER
            modified_lines.append(line)
            continue

        if perimeter_type == INTERNAL_PERIMETER:
            # End of perimeter contour
            if line.startswith("G1") and 'X' in line and 'Y' in line and 'F' in line:
                # Evaluate stored commands if stored
                if len(perimeter_contour) > 0:
                    # Find distance to closest external perimeter
                    min_distances = []
                    for perimeter_segment in perimeter_contour:
                        if 'X' in perimeter_segment or 'Y' in perimeter_segment:
                            match = re.search(r"X([-\d\.])+", perimeter_segment)
                            if match:
                                x = float(match.group(1))
                
                            match = re.search(r"Y([-\d\.])+", perimeter_segment)
                            if match:
                                y = float(match.group(1))
                        
                        min_distances.append(float("inf"))
                        for external_perimeter_segment in objects[current_object].external_perimeters[layer_num]:
                            min_distances[-1] = min(min_distances[-1], external_perimeter_segment.distance(*contour_start, x, y))
        
                        contour_start = x, y
        
                    index_count = [[0, 0]]
                    for min_distance in min_distances:
                        index = max(1, round(min_distance / perimeter_spacing)) # convert to integer value, approximates perimeter number from external one
                        for index_c in index_count:
                            if index_c[0] == index:
                                index_c[1] += 1
                                break
                        else:
                            index_count.append([index, 1])
                    # find the mode of the distances
                    index_count = sorted(index_count, key=lambda x: x[1], reverse=True)
                    index = index_count[0][0]
                    # if odd, shift down
                    if index % 2 == 1:
                        shifted_layer_z = layer_z - 0.5 * layer_height
                        modified_lines.append(f"G1 Z{shifted_layer_z:.3f}\n")
                        modified_lines.extend(perimeter_contour) # TODO: modify E values based on widths and heights
                        modified_lines.append(f"G1 Z{layer_z:.3f}\n")
                # Reset/clear all data relating to the previous contour (if any)
                inside_perimeter_contour = False
                modified_lines.append(line)
                perimeter_contour = []
            else:
                # Store all G-code commands untill a travel move is detected
                perimeter_contour.append(line)
                if not inside_perimeter_contour:
                    contour_start = previous_x, previous_y
                    inside_perimeter_contour = True
                    logging.info(f"Perimeter contour detected at layer {layer_num}")
        else:
            modified_lines.append(line)

    # Overwrite the input file with the modified G-code
    with open(input_file, 'w') as outfile:
        outfile.writelines(modified_lines)

    logging.info("G-code processing completed")
    logging.info(f"Log file saved at {log_file_path}")

# Main execution
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Post-process G-code for Z-shifting and extrusion adjustments.")
    parser.add_argument("input_file", help="Path to the input G-code file")
    parser.add_argument("-layerHeight", type=float, default=0.2, help="Layer height in mm (default: 0.2mm)")
    parser.add_argument("-extrusionMultiplier", type=float, default=1, help="Extrusion multiplier for first layer (default: 1.5x)")
    args = parser.parse_args()

    process_gcode(
        input_file=args.input_file,
        layer_height=args.layerHeight,
        extrusion_multiplier=args.extrusionMultiplier,
    )
