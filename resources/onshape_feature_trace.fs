export function cncDfmPointMm(p is Vector) returns map
{
    return
    {
        "x" : p[0] / millimeter,
        "y" : p[1] / millimeter,
        "z" : p[2] / millimeter
    };
}

export function cncDfmDirection(v is Vector) returns map
{
    return
    {
        "x" : v[0],
        "y" : v[1],
        "z" : v[2]
    };
};

export function cncDfmBoxFor(context is Context, topologyQuery is Query) returns map
{
    const entities = evaluateQuery(context, topologyQuery);
    if (size(entities) == 0)
        return {};
    const box = evBox3d(context, {
            "topology" : topologyQuery,
            "tight" : true
    });
    return
    {
        "minCorner" : cncDfmPointMm(box.minCorner),
        "maxCorner" : cncDfmPointMm(box.maxCorner)
    };
};

export function cncDfmCylinderRows(context is Context, faceQuery is Query) returns array
{
    var rows = [];
    for (var face in evaluateQuery(context, faceQuery))
    {
        const surface = evSurfaceDefinition(context, {
                "face" : face
        });
        if (surface.surfaceType != SurfaceType.CYLINDER)
            continue;
        rows = append(rows, {
                "radiusMm" : surface.radius / millimeter,
                "axisOriginMm" : cncDfmPointMm(surface.coordSystem.origin),
                "axisDirection" : cncDfmDirection(surface.coordSystem.zAxis)
        });
    }
    return rows;
};

export function cncDfmTraceFeature(context is Context, featureId is string, featureType is string) returns map
{
    const featureToken = makeId(featureId);
    const createdFaces = qCreatedBy(featureToken, EntityType.FACE);
    const createdBodies = qCreatedBy(featureToken, EntityType.BODY);
    return
    {
        "featureId" : featureId,
        "featureType" : featureType,
        "createdFaceCount" : size(evaluateQuery(context, createdFaces)),
        "createdBodyCount" : size(evaluateQuery(context, createdBodies)),
        "createdFaceQueries" : transientQueriesToStrings(evaluateQuery(context, createdFaces)),
        "createdBodyQueries" : transientQueriesToStrings(evaluateQuery(context, createdBodies)),
        "createdFaceBox" : cncDfmBoxFor(context, createdFaces),
        "createdBodyBox" : cncDfmBoxFor(context, createdBodies),
        "cylinders" : cncDfmCylinderRows(context, createdFaces)
    };
};
