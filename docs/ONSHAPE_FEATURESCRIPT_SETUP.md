# Onshape FeatureScript Helper Setup

## What This Is
This helper exists to improve geometry-to-feature traceability.

The REST feature JSON can tell us:
- feature name
- feature type
- parameter values

It does not reliably tell us which exact faces or local geometry a feature created.

The FeatureScript helper adds a reusable tracing function that can inspect:
- faces created by a feature
- bodies created by a feature
- bounding boxes for created geometry
- cylindrical faces and their radii/axes

That gives the CLI a stronger basis for matching failing STEP geometry back to the real source feature in Onshape.

## What You Need To Do
1. Open your Onshape document.
2. Create a new `Feature Studio`.
3. Open the file:
   [resources/onshape_feature_trace.fs](/Users/eoincobbe/dev/cnc-dfm/resources/onshape_feature_trace.fs)
4. Keep the auto-generated first two lines that Onshape creates at the top of the Feature Studio.
5. Copy the helper file contents and paste them below that existing header.
6. Save the Feature Studio.

You do not need to add the helper as a normal modeling feature yet.

## Current Usage
Right now the CLI uses an inline `evalFeatureScript` trace call based on the same logic as this helper file.

So this paste step is mainly for:
- visibility
- debugging
- having a reusable script in the document
- making it easier to evolve toward custom tables or attribute tagging later

## What This Helper Traces
For a given feature ID and feature type, it can report:
- created face count
- created body count
- created face transient query strings
- created body transient query strings
- created-face bounding box
- created-body bounding box
- cylindrical face rows with radius and axis

## What It Does Not Do Yet
- draw a custom table in the Part Studio
- tag geometry with persistent attributes
- directly drive automatic remediation edits by itself

Those are the next logical steps once the fingerprinting output is validated on a few real parts.
