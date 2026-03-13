"use client";

import { Suspense, useEffect, useMemo, useRef } from "react";

import { Canvas, extend, useLoader, useThree, type ThreeElement } from "@react-three/fiber";
import { Box3, BufferGeometry, Color, CylinderGeometry, DoubleSide, EdgesGeometry, Quaternion, Vector3 } from "three";
import { OrbitControls as OrbitControlsImpl } from "three/examples/jsm/controls/OrbitControls.js";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

import type { FeatureInsight } from "@/lib/types";

extend({ OrbitControls: OrbitControlsImpl });

declare module "@react-three/fiber" {
  interface ThreeElements {
    orbitControls: ThreeElement<typeof OrbitControlsImpl>;
  }
}

interface PartPreviewProps {
  previewUrl: string;
  highlightedInsights: FeatureInsight[];
  focusedInsightId: string | null;
}

function focusPoint(insight: FeatureInsight | undefined) {
  if (!insight) {
    return null;
  }
  if (insight.anchor) {
    return new Vector3(insight.anchor.x, insight.anchor.y, insight.anchor.z);
  }
  if (insight.segment_start && insight.segment_end) {
    return new Vector3(
      (insight.segment_start.x + insight.segment_end.x) / 2,
      (insight.segment_start.y + insight.segment_end.y) / 2,
      (insight.segment_start.z + insight.segment_end.z) / 2,
    );
  }
  return null;
}

function buildOffsetGeometry(source: BufferGeometry, distance: number) {
  const geometry = source.clone();
  const position = geometry.getAttribute("position");
  const normal = geometry.getAttribute("normal");

  if (!position || !normal) {
    return geometry;
  }

  for (let index = 0; index < position.count; index += 1) {
    position.setXYZ(
      index,
      position.getX(index) + normal.getX(index) * distance,
      position.getY(index) + normal.getY(index) * distance,
      position.getZ(index) + normal.getZ(index) * distance,
    );
  }

  position.needsUpdate = true;
  geometry.computeBoundingBox();
  geometry.computeBoundingSphere();
  return geometry;
}

function OverlayShell({
  geometry,
  color,
  opacity,
  offset,
  center,
}: {
  geometry: BufferGeometry;
  color: string;
  opacity: number;
  offset: number;
  center: Vector3;
}) {
  const liftedGeometry = useMemo(() => buildOffsetGeometry(geometry, offset), [geometry, offset]);

  useEffect(() => {
    return () => {
      liftedGeometry.dispose();
    };
  }, [liftedGeometry]);

  return (
    <mesh geometry={liftedGeometry} position={[-center.x, -center.y, -center.z]} renderOrder={3}>
      <meshBasicMaterial
        color={color}
        depthWrite={false}
        opacity={opacity}
        side={DoubleSide}
        toneMapped={false}
        transparent
      />
    </mesh>
  );
}

function CreaseLines({
  geometry,
  center,
}: {
  geometry: BufferGeometry;
  center: Vector3;
}) {
  const creaseGeometry = useMemo(() => new EdgesGeometry(geometry, 8), [geometry]);

  useEffect(() => {
    return () => {
      creaseGeometry.dispose();
    };
  }, [creaseGeometry]);

  return (
    <lineSegments geometry={creaseGeometry} position={[-center.x, -center.y, -center.z]} renderOrder={2}>
      <lineBasicMaterial color="#111827" toneMapped={false} transparent opacity={0.9} />
    </lineSegments>
  );
}

function SegmentHighlight({
  start,
  end,
  center,
  color,
  radius,
}: {
  start: Vector3;
  end: Vector3;
  center: Vector3;
  color: string;
  radius: number;
}) {
  const { geometry, midpoint, quaternion } = useMemo(() => {
    const vector = end.clone().sub(start);
    const length = Math.max(vector.length(), 0.001);
    const midpoint = start.clone().add(end).multiplyScalar(0.5).sub(center);
    const quaternion = new Quaternion().setFromUnitVectors(
      new Vector3(0, 1, 0),
      vector.clone().normalize(),
    );

    return {
      geometry: new CylinderGeometry(radius, radius, length, 10),
      midpoint,
      quaternion,
    };
  }, [center, end, radius, start]);

  useEffect(() => {
    return () => {
      geometry.dispose();
    };
  }, [geometry]);

  return (
    <mesh geometry={geometry} position={midpoint} quaternion={quaternion} renderOrder={4}>
      <meshBasicMaterial color={color} depthWrite={false} toneMapped={false} transparent opacity={0.96} />
    </mesh>
  );
}

function OrbitController({
  radius,
  target,
}: {
  radius: number;
  target: Vector3;
}) {
  const controls = useRef<OrbitControlsImpl>(null);
  const { camera, gl } = useThree();

  useEffect(() => {
    camera.position.set(
      target.x + radius * 1.45,
      target.y + radius * 1.05,
      target.z + radius * 1.8,
    );
    camera.lookAt(target);
    controls.current?.target.copy(target);
    controls.current?.update();
  }, [camera, radius, target]);

  return <orbitControls ref={controls} args={[camera, gl.domElement]} enableDamping dampingFactor={0.08} />;
}

function Scene({
  previewUrl,
  highlightedInsights,
  focusedInsightId,
}: PartPreviewProps) {
  const previewGeometry = useLoader(STLLoader, previewUrl);
  const overlayUrls = Array.from(new Set(highlightedInsights.flatMap((insight) => insight.overlay_mesh_paths)));
  const loadedOverlayGeometries = useLoader(STLLoader, overlayUrls.length > 0 ? overlayUrls : [previewUrl]);
  const overlayGeometries = overlayUrls.length > 0 ? loadedOverlayGeometries : [];

  previewGeometry.computeBoundingBox();
  const bounds = previewGeometry.boundingBox?.clone() ?? new Box3(new Vector3(-1, -1, -1), new Vector3(1, 1, 1));
  const center = bounds.getCenter(new Vector3());
  const size = bounds.getSize(new Vector3());
  const radius = Math.max(size.length() / 2, 1);
  const focusedInsight = highlightedInsights.find((insight) => insight.id === focusedInsightId) ?? highlightedInsights[0];
  const nextTarget = focusPoint(focusedInsight)?.sub(center) ?? new Vector3(0, 0, 0);

  return (
    <>
      <ambientLight intensity={0.7} />
      <directionalLight intensity={1.4} position={[radius * 1.5, radius, radius * 2]} />
      <OrbitController radius={radius} target={nextTarget} />
      <group>
        <mesh geometry={previewGeometry} position={[-center.x, -center.y, -center.z]}>
          <meshStandardMaterial color={new Color("#edf2fa")} metalness={0} roughness={0.62} />
        </mesh>

        <CreaseLines center={center} geometry={previewGeometry} />

        {overlayUrls.map((url, index) => {
          const focused = highlightedInsights.some((insight) => insight.id === focusedInsightId && insight.overlay_mesh_paths.includes(url));
          return (
            <group key={url}>
              <OverlayShell
                center={center}
                color={focused ? "#1247bf" : "#6bc0ff"}
                geometry={overlayGeometries[index]}
                offset={focused ? 0.12 : 0.08}
                opacity={focused ? 0.82 : 0.56}
              />
              <OverlayShell
                center={center}
                color={focused ? "#1247bf" : "#6bc0ff"}
                geometry={overlayGeometries[index]}
                offset={focused ? -0.12 : -0.08}
                opacity={focused ? 0.82 : 0.56}
              />
            </group>
          );
        })}

        {highlightedInsights.map((insight) => {
          if (!insight.segment_start || !insight.segment_end) {
            return null;
          }

          const focused = insight.id === focusedInsightId;
          const start = new Vector3(insight.segment_start.x, insight.segment_start.y, insight.segment_start.z);
          const end = new Vector3(insight.segment_end.x, insight.segment_end.y, insight.segment_end.z);

          return (
            <SegmentHighlight
              key={insight.id}
              center={center}
              color={focused ? "#0f56d8" : "#66b4ff"}
              end={end}
              radius={focused ? 0.72 : 0.48}
              start={start}
            />
          );
        })}
      </group>
    </>
  );
}

export function PartPreview(props: PartPreviewProps) {
  return (
    <Canvas camera={{ fov: 32 }} dpr={[1, 2]}>
      <Suspense fallback={null}>
        <Scene {...props} />
      </Suspense>
    </Canvas>
  );
}
