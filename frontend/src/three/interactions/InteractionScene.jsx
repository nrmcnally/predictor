import { useEffect, useRef } from "react";
import * as THREE from "three";

const COLORS = {
  red: 0xff3355,
  blue: 0x3d7bff,
  gold: 0xf5c451,
  green: 0x2fd58b,
  amber: 0xfba94c,
  floor: 0x111827,
};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function createMaterial(color, opacity = 1) {
  return new THREE.MeshBasicMaterial({
    color,
    transparent: opacity < 1,
    opacity,
  });
}

function createDisc(radius, color, opacity = 0.38) {
  const shape = new THREE.Shape();

  for (let index = 0; index <= 8; index += 1) {
    const angle = (index / 8) * Math.PI * 2 + Math.PI / 8;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;

    if (index === 0) {
      shape.moveTo(x, y);
    } else {
      shape.lineTo(x, y);
    }
  }

  const mesh = new THREE.Mesh(
    new THREE.ShapeGeometry(shape),
    createMaterial(color, opacity)
  );
  mesh.rotation.x = -Math.PI / 2;
  return mesh;
}

function setOpacity(object, opacity) {
  object.traverse((child) => {
    if (child.material?.opacity !== undefined) {
      child.material.opacity += (opacity - child.material.opacity) * 0.16;
    }
  });
}

function buildRevealScene() {
  const group = new THREE.Group();
  const floor = createDisc(3.15, COLORS.floor, 0.48);
  const outerAura = createDisc(2.9, COLORS.gold, 0.04);
  const innerAura = createDisc(1.15, COLORS.gold, 0.06);
  const splitAura = createDisc(1.58, COLORS.amber, 0.01);
  outerAura.position.y = 0.025;
  innerAura.position.y = 0.04;
  splitAura.position.y = 0.055;

  group.add(floor, outerAura, innerAura, splitAura);

  const red = new THREE.Mesh(
    new THREE.SphereGeometry(0.36, 32, 18),
    createMaterial(COLORS.red, 0.95)
  );
  const blue = new THREE.Mesh(
    new THREE.SphereGeometry(0.36, 32, 18),
    createMaterial(COLORS.blue, 0.95)
  );
  const verdict = new THREE.Mesh(
    new THREE.BoxGeometry(1.48, 0.12, 0.58),
    createMaterial(COLORS.gold, 0.18)
  );
  const core = new THREE.Mesh(
    new THREE.SphereGeometry(0.18, 32, 18),
    createMaterial(COLORS.gold, 0.16)
  );

  red.position.set(-2.15, 0.45, 0.55);
  blue.position.set(2.15, 0.45, -0.55);
  verdict.position.set(0, 0.35, 0);
  core.position.set(0, 0.45, 0);

  const redShadow = createDisc(0.54, COLORS.red, 0.2);
  const blueShadow = createDisc(0.54, COLORS.blue, 0.2);
  const centerPulse = createDisc(0.46, COLORS.gold, 0.08);
  redShadow.position.set(red.position.x, 0.04, red.position.z);
  blueShadow.position.set(blue.position.x, 0.04, blue.position.z);
  centerPulse.position.set(0, 0.07, 0);

  const evidenceSpecs = [
    {
      color: COLORS.red,
      point: [-0.68, 0.58, 0.16],
    },
    {
      color: COLORS.green,
      point: [-0.08, 0.74, -0.18],
    },
    {
      color: COLORS.amber,
      point: [0.42, 0.6, 0.12],
    },
  ];
  const evidenceObjects = evidenceSpecs.map((spec) => {
    const node = new THREE.Mesh(
      new THREE.SphereGeometry(0.1, 22, 14),
      createMaterial(spec.color, 0.12)
    );
    const halo = createDisc(0.2, spec.color, 0.08);
    const ripple = createDisc(0.34, spec.color, 0.06);

    node.position.set(...spec.point);
    halo.position.set(spec.point[0], 0.06, spec.point[2]);
    ripple.position.set(spec.point[0], 0.04, spec.point[2]);
    group.add(node, halo, ripple);
    return { node, halo, ripple };
  });

  const impactFields = [0.48, 0.76, 1.04].map((radius, index) => {
    const colors = [COLORS.red, COLORS.gold, COLORS.amber];
    const field = createDisc(radius, colors[index], 0.01);
    field.position.set(-0.08, 0.08 + index * 0.012, 0);
    group.add(field);
    return field;
  });

  const submissionFields = [0.46, 0.68, 0.9].map((radius, index) => {
    const colors = [COLORS.green, COLORS.gold, COLORS.blue];
    const field = createDisc(radius, colors[index], 0.01);
    field.position.set(0.28, 0.12 + index * 0.045, -0.18);
    group.add(field);
    return field;
  });

  const decisionPlates = [-0.46, 0, 0.46].map((x, index) => {
    const plate = new THREE.Mesh(
      new THREE.BoxGeometry(0.28, 0.07, 0.38),
      createMaterial(COLORS.gold, 0.01)
    );
    plate.position.set(x, 0.24 + index * 0.02, 0.7);
    plate.rotation.y = (index - 1) * 0.14;
    group.add(plate);
    return plate;
  });

  group.add(redShadow, blueShadow, centerPulse, red, blue, verdict, core);
  group.userData = {
    red,
    blue,
    verdict,
    core,
    redShadow,
    blueShadow,
    centerPulse,
    outerAura,
    innerAura,
    splitAura,
    evidenceObjects,
    impactFields,
    submissionFields,
    decisionPlates,
  };
  return group;
}

function updateReveal(
  root,
  elapsed,
  phase,
  confidence = 64.5,
  marketSplit = false,
  evidenceIndex = -1,
  finishType = "decision"
) {
  const lock = phase === "lock";
  const scan = phase === "scan" || phase.startsWith("evidence");
  const result = phase === "result";
  const methodCue = phase === "evidence-2" || result;
  const isKo = finishType === "ko";
  const isSubmission = finishType === "submission";
  const isDecision = finishType === "decision";
  const pulse = (Math.sin(elapsed * 5) + 1) / 2;
  const warningPulse = (Math.sin(elapsed * 7) + 1) / 2;
  const probability = clamp(confidence / 100, 0.5, 0.85);
  const dominance = clamp((probability - 0.5) / 0.3, 0.05, 1);
  const data = root.userData;
  const activeBump =
    evidenceIndex === 0
      ? 0.42
      : evidenceIndex === 1
        ? 0.62
        : evidenceIndex === 2
          ? -0.18
          : 0;
  const bob = Math.sin(elapsed * 5.2) * 0.035;
  const feint = Math.sin(elapsed * 8.4) * 0.08;
  const koSnap = isKo && methodCue ? 0.34 + pulse * 0.18 : 0;
  const submissionDraw = isSubmission && methodCue ? 0.26 + pulse * 0.05 : 0;

  root.rotation.y = Math.sin(elapsed * 0.34) * (result ? 0.07 : 0.14);
  const redX = result
    ? -0.58 + dominance * 0.2 + koSnap + submissionDraw
    : scan
      ? -1.34 + activeBump + feint + (methodCue && isKo ? 0.18 : 0)
      : lock
        ? -1.52
      : -2.15;
  const blueX = result
    ? 1.95 + dominance * 0.5 - submissionDraw + (isKo ? 0.18 : 0)
    : scan
      ? 1.34 - activeBump * 0.42 - feint * 0.5 - (methodCue && isSubmission ? 0.18 : 0)
      : lock
        ? 1.52
      : 2.15;
  const redZ = result
    ? 0.06 - (isSubmission ? 0.16 : 0)
    : scan
      ? 0.32 - activeBump * 0.18 - (methodCue && isSubmission ? 0.12 : 0)
      : 0.55;
  const blueZ = result
    ? -0.44 + (isSubmission ? 0.18 : 0)
    : scan
      ? -0.32 + activeBump * 0.1 + (methodCue && isSubmission ? 0.1 : 0)
      : -0.55;
  const redY = result ? 0.62 + dominance * 0.1 : 0.45 + (scan ? bob : 0);
  const blueY = result ? 0.28 - (isKo ? 0.08 : 0) : 0.45 - (scan ? bob * 0.7 : 0);

  data.red.position.x += (redX - data.red.position.x) * 0.09;
  data.red.position.y += (redY - data.red.position.y) * 0.09;
  data.red.position.z += (redZ - data.red.position.z) * 0.09;
  data.blue.position.x += (blueX - data.blue.position.x) * 0.09;
  data.blue.position.y += (blueY - data.blue.position.y) * 0.09;
  data.blue.position.z += (blueZ - data.blue.position.z) * 0.09;
  data.red.scale.setScalar(result ? 1.12 + dominance * 0.22 + (isKo ? 0.08 : 0) : 1);
  data.blue.scale.setScalar(result ? 0.76 + (1 - dominance) * 0.14 - (isKo ? 0.08 : 0) : 1);
  data.core.scale.setScalar(scan ? 1.18 + pulse * 0.52 : result ? 1.35 + dominance * 0.3 : 0.9);
  data.verdict.scale.x += ((result ? 1.1 + dominance * 0.22 : 0.35) - data.verdict.scale.x) * 0.12;
  data.verdict.scale.z += ((result ? 1 : 0.35) - data.verdict.scale.z) * 0.12;
  data.redShadow.position.x = data.red.position.x;
  data.redShadow.position.z = data.red.position.z;
  data.blueShadow.position.x = data.blue.position.x;
  data.blueShadow.position.z = data.blue.position.z;
  data.redShadow.scale.setScalar(result ? 1.12 + dominance * 0.25 : scan ? 1.04 + pulse * 0.08 : 1);
  data.blueShadow.scale.setScalar(result ? 0.78 : scan ? 1.02 - pulse * 0.05 : 1);
  data.centerPulse.scale.setScalar(scan ? 1.1 + pulse * 0.42 : result ? 1.32 + dominance * 0.18 : 0.9);

  setOpacity(data.verdict, result ? 0.68 + dominance * 0.18 : 0.16);
  setOpacity(data.redShadow, result ? 0.42 : scan || lock ? 0.28 : 0.2);
  setOpacity(data.blueShadow, result ? 0.12 : scan || lock ? 0.24 : 0.2);
  setOpacity(data.centerPulse, scan ? 0.32 : result ? 0.18 : 0.08);
  setOpacity(data.innerAura, scan ? 0.08 + pulse * 0.03 : result ? 0.1 : 0.05);
  setOpacity(data.splitAura, marketSplit && (phase.startsWith("evidence") || result) ? 0.12 + warningPulse * 0.12 : 0.01);

  data.impactFields.forEach((field, index) => {
    const visible = isKo && methodCue;
    const stagger = index * 0.18;
    const wave = (pulse + stagger) % 1;
    field.position.x = (data.red.position.x + data.blue.position.x) / 2 - 0.18;
    field.position.z = (data.red.position.z + data.blue.position.z) / 2;
    field.scale.setScalar(visible ? 0.82 + wave * (0.44 + index * 0.14) : 0.72);
    setOpacity(field, visible ? 0.18 - index * 0.035 : 0.01);
  });

  data.submissionFields.forEach((field, index) => {
    const visible = isSubmission && methodCue;
    const closing = 1.18 - pulse * 0.18 - index * 0.08;
    field.position.x = data.blue.position.x - 0.24 + index * 0.03;
    field.position.z = data.blue.position.z + 0.04;
    field.position.y = 0.1 + index * 0.035 + pulse * 0.02;
    field.rotation.z = elapsed * (0.18 + index * 0.06);
    field.scale.setScalar(visible ? closing : 1.08);
    setOpacity(field, visible ? 0.16 - index * 0.025 : 0.01);
  });

  data.decisionPlates.forEach((plate, index) => {
    const visible = isDecision && result;
    const settle = visible ? 1 + Math.sin(elapsed * 3.4 + index) * 0.03 : 0.72;
    plate.position.y = 0.24 + index * 0.02 + (visible ? pulse * 0.025 : 0);
    plate.rotation.y = (index - 1) * 0.14 + (visible ? Math.sin(elapsed * 1.6 + index) * 0.04 : 0);
    plate.scale.setScalar(settle);
    setOpacity(plate, visible ? 0.48 : 0.01);
  });

  data.evidenceObjects.forEach((objects, index) => {
    const active = index === evidenceIndex;
    const revealed = evidenceIndex >= index || result;
    const opacity = result ? 0.05 : active ? 0.88 : revealed ? 0.12 : 0.04;
    const scale = active ? 1.28 : revealed ? 0.94 : 0.86;

    setOpacity(objects.node, opacity);
    setOpacity(objects.halo, result ? 0.04 : active ? 0.58 : revealed ? 0.1 : 0.04);
    setOpacity(objects.ripple, result ? 0.03 : active ? 0.34 + pulse * 0.18 : 0.04);
    objects.node.scale.setScalar(scale);
    objects.halo.scale.setScalar(scale);
    objects.ripple.scale.setScalar(active ? 1.08 + pulse * 0.8 : 0.82);
  });
}

export default function InteractionScene({
  phase = "idle",
  confidence = 64.5,
  marketSplit = false,
  evidenceIndex = -1,
  finishType = "decision",
}) {
  const containerRef = useRef(null);
  const stateRef = useRef({ phase, confidence, marketSplit, evidenceIndex, finishType });

  useEffect(() => {
    stateRef.current = { phase, confidence, marketSplit, evidenceIndex, finishType };
  }, [phase, confidence, marketSplit, evidenceIndex, finishType]);

  useEffect(() => {
    const container = containerRef.current;

    if (!container) {
      return undefined;
    }

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x05060a, 7.5, 15);

    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 50);
    camera.position.set(0, 3.05, 6.7);

    const root = buildRevealScene();
    scene.add(root);

    function resize() {
      const width = container.clientWidth || 1;
      const height = container.clientHeight || 1;
      const narrow = width < 520;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.fov = narrow ? 52 : 42;
      camera.position.y = narrow ? 3.4 : 3.05;
      camera.position.z = narrow ? 7.8 : 6.7;
      camera.updateProjectionMatrix();
    }

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    resize();

    const clock = new THREE.Clock();
    let frameId = 0;

    function renderFrame() {
      const elapsed = clock.getElapsedTime();
      const current = stateRef.current;

      updateReveal(
        root,
        elapsed,
        current.phase,
        current.confidence,
        current.marketSplit,
        current.evidenceIndex,
        current.finishType
      );

      camera.lookAt(0, 0.18, 0);
      renderer.render(scene, camera);
      frameId = window.requestAnimationFrame(renderFrame);
    }

    renderFrame();

    return () => {
      window.cancelAnimationFrame(frameId);
      resizeObserver.disconnect();

      scene.traverse((object) => {
        object.geometry?.dispose?.();
        const materials = Array.isArray(object.material)
          ? object.material
          : object.material
            ? [object.material]
            : [];

        for (const material of materials) {
          material.dispose?.();
        }
      });

      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return <div ref={containerRef} className="interaction-canvas variant-reveal" />;
}
