import { useEffect, useRef } from "react";
import * as THREE from "three";

const CAGE_RADIUS = 3.1;
const CAGE_HEIGHT = 1.9;
const SIDES = 8;

function buildOctagonRing(radius, y) {
  const points = [];

  for (let index = 0; index <= SIDES; index += 1) {
    const angle = (index / SIDES) * Math.PI * 2 + Math.PI / SIDES;
    points.push(new THREE.Vector3(Math.cos(angle) * radius, y, Math.sin(angle) * radius));
  }

  return points;
}

function buildCage() {
  const group = new THREE.Group();

  const ringMaterial = new THREE.LineBasicMaterial({
    color: 0x5d6b9e,
    transparent: true,
    opacity: 0.9,
  });

  const meshMaterial = new THREE.LineBasicMaterial({
    color: 0x39436b,
    transparent: true,
    opacity: 0.38,
  });

  const topRing = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(buildOctagonRing(CAGE_RADIUS, CAGE_HEIGHT)),
    ringMaterial
  );

  const bottomRing = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(buildOctagonRing(CAGE_RADIUS, 0)),
    ringMaterial
  );

  group.add(topRing, bottomRing);

  // Vertical posts plus a sparse chain-link suggestion on each panel.
  const fencePoints = [];

  for (let side = 0; side < SIDES; side += 1) {
    const angleA = (side / SIDES) * Math.PI * 2 + Math.PI / SIDES;
    const angleB = ((side + 1) / SIDES) * Math.PI * 2 + Math.PI / SIDES;

    const cornerA = new THREE.Vector3(
      Math.cos(angleA) * CAGE_RADIUS,
      0,
      Math.sin(angleA) * CAGE_RADIUS
    );
    const cornerB = new THREE.Vector3(
      Math.cos(angleB) * CAGE_RADIUS,
      0,
      Math.sin(angleB) * CAGE_RADIUS
    );

    fencePoints.push(cornerA.clone(), cornerA.clone().setY(CAGE_HEIGHT));

    const STEPS = 4;

    for (let step = 0; step <= STEPS; step += 1) {
      const t = step / STEPS;
      const base = cornerA.clone().lerp(cornerB, t);
      const next = cornerA.clone().lerp(cornerB, Math.min(1, t + 1 / STEPS));

      if (step < STEPS) {
        fencePoints.push(base.clone(), next.clone().setY(CAGE_HEIGHT));
        fencePoints.push(base.clone().setY(CAGE_HEIGHT), next.clone());
      }
    }
  }

  const fenceGeometry = new THREE.BufferGeometry().setFromPoints(fencePoints);
  group.add(new THREE.LineSegments(fenceGeometry, meshMaterial));

  // Glowing canvas floor.
  const floorShape = new THREE.Shape();
  buildOctagonRing(CAGE_RADIUS, 0).forEach((point, index) => {
    if (index === 0) {
      floorShape.moveTo(point.x, point.z);
    } else {
      floorShape.lineTo(point.x, point.z);
    }
  });

  const floor = new THREE.Mesh(
    new THREE.ShapeGeometry(floorShape),
    new THREE.MeshBasicMaterial({
      color: 0x141a2e,
      transparent: true,
      opacity: 0.55,
      side: THREE.DoubleSide,
    })
  );
  floor.rotation.x = -Math.PI / 2;
  floor.position.y = 0.001;
  group.add(floor);

  return group;
}

function buildCornerGlow(color, position) {
  const texture = (() => {
    const size = 128;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const context = canvas.getContext("2d");
    const gradient = context.createRadialGradient(
      size / 2, size / 2, 0,
      size / 2, size / 2, size / 2
    );
    gradient.addColorStop(0, "rgba(255,255,255,0.9)");
    gradient.addColorStop(0.25, "rgba(255,255,255,0.35)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    context.fillStyle = gradient;
    context.fillRect(0, 0, size, size);
    return new THREE.CanvasTexture(canvas);
  })();

  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: texture,
      color,
      transparent: true,
      opacity: 0.8,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
  sprite.position.copy(position);
  sprite.scale.set(3.4, 3.4, 1);

  return sprite;
}

function buildParticles() {
  const COUNT = 380;
  const positions = new Float32Array(COUNT * 3);
  const colors = new Float32Array(COUNT * 3);
  const red = new THREE.Color(0xff3355);
  const blue = new THREE.Color(0x3d7bff);
  const white = new THREE.Color(0xaab4d4);

  for (let index = 0; index < COUNT; index += 1) {
    positions[index * 3] = (Math.random() - 0.5) * 14;
    positions[index * 3 + 1] = Math.random() * 5.5 - 0.5;
    positions[index * 3 + 2] = (Math.random() - 0.5) * 10;

    const roll = Math.random();
    const color = roll < 0.3 ? red : roll < 0.6 ? blue : white;
    colors[index * 3] = color.r;
    colors[index * 3 + 1] = color.g;
    colors[index * 3 + 2] = color.b;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));

  const material = new THREE.PointsMaterial({
    size: 0.035,
    vertexColors: true,
    transparent: true,
    opacity: 0.85,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });

  return new THREE.Points(geometry, material);
}

export default function OctagonScene({ className = "" }) {
  const containerRef = useRef(null);

  useEffect(() => {
    const container = containerRef.current;

    if (!container) {
      return undefined;
    }

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x06070b, 8, 16);

    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 60);
    camera.position.set(0, 2.4, 8.2);

    const stage = new THREE.Group();
    const cage = buildCage();
    stage.add(cage);

    // Red and blue corner glows sit on opposite corners of the cage.
    stage.add(buildCornerGlow(0xff3355, new THREE.Vector3(-CAGE_RADIUS * 0.95, 0.9, 0.4)));
    stage.add(buildCornerGlow(0x3d7bff, new THREE.Vector3(CAGE_RADIUS * 0.95, 0.9, -0.4)));

    const particles = buildParticles();
    stage.add(particles);
    scene.add(stage);

    const pointer = { x: 0, y: 0 };

    function handlePointerMove(event) {
      const bounds = container.getBoundingClientRect();
      pointer.x = ((event.clientX - bounds.left) / bounds.width - 0.5) * 2;
      pointer.y = ((event.clientY - bounds.top) / bounds.height - 0.5) * 2;
    }

    container.addEventListener("pointermove", handlePointerMove);

    function resize() {
      const width = container.clientWidth || 1;
      const height = container.clientHeight || 1;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    }

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    resize();

    const clock = new THREE.Clock();
    let frameId = 0;

    function renderFrame() {
      const elapsed = clock.getElapsedTime();

      cage.rotation.y = elapsed * 0.07;
      particles.rotation.y = -elapsed * 0.015;

      camera.position.x += (pointer.x * 0.7 - camera.position.x) * 0.04;
      camera.position.y += (2.4 - pointer.y * 0.4 - camera.position.y) * 0.04;
      camera.lookAt(0, 0.75, 0);

      renderer.render(scene, camera);
    }

    function animate() {
      renderFrame();
      frameId = window.requestAnimationFrame(animate);
    }

    if (reducedMotion) {
      renderFrame();
    } else {
      animate();
    }

    return () => {
      window.cancelAnimationFrame(frameId);
      resizeObserver.disconnect();
      container.removeEventListener("pointermove", handlePointerMove);

      scene.traverse((object) => {
        object.geometry?.dispose?.();

        const materials = Array.isArray(object.material)
          ? object.material
          : object.material
            ? [object.material]
            : [];

        for (const material of materials) {
          material.map?.dispose?.();
          material.dispose?.();
        }
      });

      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return <div ref={containerRef} className={`octagon-scene ${className}`} aria-hidden="true" />;
}
