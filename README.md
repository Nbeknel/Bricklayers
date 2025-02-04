# Bricklayers
This is a script to add Brick layers to SuperSlicer (might be broken for Prusaslicer and Orcaslicer).
(As of now it doesn't work with Bambu printers)

To use it you need to have Python installed. (www.python.org) 

In SuperSlicer's printsettings go to "Output options". There you will find a section called "Post processing scripts". 
You can add the following to run the script:

```"C:\Your\Path\To\Python\python.exe" "C:\Your\Path\To\Script\bricklayers.py"```

Ensure `Label objects` is ticked.

There is one parameter you can add. -extrusionMultiplier, although it currently does nothing.

```"C:\Your\Path\To\Python\python.exe" "C:\Your\Path\To\Script\bricklayers.py" -extrusionMultiplier 1.3```

## Changes to original
* The intenal perimeter 'parity' is now calculated by finding the mode of shortests distances to the external perimeter. this distance is divided by the perimeter spacing and rounded to the nearest integer.
* Perimeters are shifted downwards starting from the second layer. This ensures safe travel moves with no z-hop. This also makes the cross-section of extrusion lines smaller, not larger, so as not to exceed limits set in the printer firmware.
* Should work with `Variable layer height`, or if the plater has two objects with different layer heights.

## Drawbacks
* Current implementation does not change the extrusion value when shifting down.
* Current implementation does not compensate for flow.
* Does not shift down perimeters if current layer has overhang perimeters or top solid layers. For the former, there are situations when the 'external perimeter' lies completely inside a overhang perimeter. Finding them requires even more code. For the latter, it is to ensure an flat surface around the top solid infill.
* Currently works only with Octoprint object labeling.
