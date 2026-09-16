import React, { useEffect, useRef, useState, useCallback } from 'react';
import * as THREE from 'three';
import {
  createBobTeacher,
  createAliceStudent,
  createCharlieStudent,
  createDeskAndChair,
  createDeskProps,
  CharacterRig,
} from './proceduralCharacters';
import { loadMixamoFBXAvatar } from './fbxAvatarLoader';
import { loadGLBAvatar } from './gltfAvatarLoader';
import { createBlackboardCanvas } from './blackboardCanvas';
import { BlackboardData, CameraViewMode, ScreenCoord, SpeakerId } from '../types';

interface Classroom3DProps {
  blackboardData: BlackboardData;
  activeSpeaker: SpeakerId | null;
  activeEmotion?: string;
  activeGesture?: string;
  cameraMode: CameraViewMode;
  onCoordinatesUpdate: (coords: Record<SpeakerId, ScreenCoord>) => void;
  onCameraModeChange?: (mode: CameraViewMode) => void;
}

export const Classroom3D: React.FC<Classroom3DProps> = ({
  blackboardData,
  activeSpeaker,
  activeGesture,
  cameraMode,
  onCoordinatesUpdate,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const bobRigRef = useRef<CharacterRig | null>(null);
  const aliceRigRef = useRef<CharacterRig | null>(null);
  const charlieRigRef = useRef<CharacterRig | null>(null);
  const userAnchorRef = useRef<THREE.Object3D | null>(null);
  const blackboardCanvasRef = useRef<ReturnType<typeof createBlackboardCanvas> | null>(null);
  const blackboardTextureRef = useRef<THREE.CanvasTexture | null>(null);

  // Camera look state
  const isDraggingRef = useRef<boolean>(false);
  const cameraEulerRef = useRef<THREE.Euler>(new THREE.Euler(0, 0, 0, 'YXZ'));
  const targetCameraPosRef = useRef<THREE.Vector3>(new THREE.Vector3(0, 1.25, 0.8));
  const targetCameraLookRef = useRef<THREE.Vector3>(new THREE.Vector3(0, 1.45, -4.5));
  const [hintDismissed, setHintDismissed] = useState(false);

  // Update blackboard texture whenever data changes
  useEffect(() => {
    if (blackboardCanvasRef.current && blackboardTextureRef.current) {
      blackboardCanvasRef.current.updateContent(blackboardData);
      blackboardTextureRef.current.needsUpdate = true;
    }
  }, [blackboardData]);

  // Update character gestures according to speaker
  useEffect(() => {
    if (!activeSpeaker) return;
    if (activeSpeaker === 'bob' && bobRigRef.current) {
      bobRigRef.current.setGesture(activeGesture || 'point_chalkboard');
    } else if (bobRigRef.current) {
      bobRigRef.current.setGesture('idle');
    }

    if (activeSpeaker === 'alice' && aliceRigRef.current) {
      aliceRigRef.current.setGesture(activeGesture || 'lean_forward');
    } else if (aliceRigRef.current) {
      aliceRigRef.current.setGesture('idle');
    }

    if (activeSpeaker === 'charlie' && charlieRigRef.current) {
      charlieRigRef.current.setGesture(activeGesture || 'confused_tilt');
    } else if (charlieRigRef.current) {
      charlieRigRef.current.setGesture('idle');
    }
  }, [activeSpeaker, activeGesture]);

  // Adjust camera targets based on cameraMode
  useEffect(() => {
    if (cameraMode === 'desk_pov') {
      targetCameraPosRef.current.set(0, 1.22, 0.75); // Seated at user desk
      targetCameraLookRef.current.set(0, 1.4, -4.5);
    } else if (cameraMode === 'blackboard_focus') {
      targetCameraPosRef.current.set(0.2, 1.5, -1.8); // Zoom in on Bob & Board
      targetCameraLookRef.current.set(0.1, 1.6, -4.8);
    } else if (cameraMode === 'classmate_focus') {
      targetCameraPosRef.current.set(0, 1.35, 0.1); // Slightly pulled back showing Alice & Charlie
      targetCameraLookRef.current.set(0, 1.2, -1.5);
    } else if (cameraMode === 'free_orbit') {
      targetCameraPosRef.current.set(0, 2.2, 3.2); // Overhead wide classroom overview
      targetCameraLookRef.current.set(0, 1.3, -2.5);
    }
  }, [cameraMode]);

  const projectToScreen = useCallback(
    (object3D: THREE.Object3D, camera: THREE.PerspectiveCamera, width: number, height: number): ScreenCoord => {
      const v = new THREE.Vector3();
      object3D.getWorldPosition(v);
      v.project(camera);

      // Check if within visible frustum
      const isVisible = v.z < 1.0 && v.z > -1.0;
      const x = (v.x * 0.5 + 0.5) * width;
      const y = (-(v.y * 0.5) + 0.5) * height;

      return {
        x,
        y,
        visible: isVisible && x > -50 && x < width + 50 && y > -50 && y < height + 50,
      };
    },
    []
  );

  // Initialize Scene
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const width = container.clientWidth;
    const height = container.clientHeight;

    // 1. Scene & Camera
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xdce7ee); // Soft classroom daylight
    scene.fog = new THREE.FogExp2(0xdce7ee, 0.02);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(62, width / height, 0.1, 50);
    camera.position.copy(targetCameraPosRef.current);
    camera.lookAt(targetCameraLookRef.current);
    cameraRef.current = camera;

    // 2. WebGL Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // 3. Lighting (Warm classroom sun from windows + ceiling lights)
    const ambientLight = new THREE.AmbientLight(0xfff7ed, 0.85);
    scene.add(ambientLight);

    // Sunlight from left window
    const sunLight = new THREE.DirectionalLight(0xfffaea, 1.4);
    sunLight.position.set(-8, 7, 2);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 2048;
    sunLight.shadow.mapSize.height = 2048;
    sunLight.shadow.camera.near = 0.5;
    sunLight.shadow.camera.far = 25;
    sunLight.shadow.camera.left = -8;
    sunLight.shadow.camera.right = 8;
    sunLight.shadow.camera.top = 8;
    sunLight.shadow.camera.bottom = -8;
    sunLight.shadow.bias = -0.0005;
    scene.add(sunLight);

    // Ceiling fill light near board
    const boardSpot = new THREE.PointLight(0xffffff, 0.9, 8);
    boardSpot.position.set(0, 3.8, -3.5);
    scene.add(boardSpot);

    // 4. Classroom Architecture
    // Floor (Warm parquet wood)
    const floorGeom = new THREE.PlaneGeometry(16, 18);
    const floorMat = new THREE.MeshStandardMaterial({
      color: 0xdfcbaf, // Warm classroom parquet
      roughness: 0.35,
      metalness: 0.05,
    });
    const floor = new THREE.Mesh(floorGeom, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(0, 0, -1);
    floor.receiveShadow = true;
    scene.add(floor);

    // Front Wall (behind chalkboard)
    const frontWallMat = new THREE.MeshStandardMaterial({ color: 0xefe9db, roughness: 0.8 });
    const frontWall = new THREE.Mesh(new THREE.PlaneGeometry(16, 5), frontWallMat);
    frontWall.position.set(0, 2.5, -5.5);
    frontWall.receiveShadow = true;
    scene.add(frontWall);

    // Wainscot / wall molding strip
    const molding = new THREE.Mesh(
      new THREE.BoxGeometry(16, 0.1, 0.05),
      new THREE.MeshStandardMaterial({ color: 0x7a8b84 })
    );
    molding.position.set(0, 1.1, -5.48);
    scene.add(molding);

    const lowerWall = new THREE.Mesh(
      new THREE.PlaneGeometry(16, 1.1),
      new THREE.MeshStandardMaterial({ color: 0x82968d, roughness: 0.7 })
    );
    lowerWall.position.set(0, 0.55, -5.49);
    scene.add(lowerWall);

    // Back Wall
    const backWall = new THREE.Mesh(new THREE.PlaneGeometry(16, 5), frontWallMat);
    backWall.position.set(0, 2.5, 7.5);
    backWall.rotation.y = Math.PI;
    scene.add(backWall);

    // Left Wall with large window frames
    const leftWallMat = new THREE.MeshStandardMaterial({ color: 0xf5eedf, roughness: 0.85 });
    const leftWall = new THREE.Mesh(new THREE.PlaneGeometry(18, 5), leftWallMat);
    leftWall.position.set(-6, 2.5, 0);
    leftWall.rotation.y = Math.PI / 2;
    scene.add(leftWall);

    // Large classroom windows on left wall
    const windowFrameMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.4 });
    const glassMat = new THREE.MeshBasicMaterial({ color: 0xcbe4f7, transparent: true, opacity: 0.65 });
    for (let i = 0; i < 3; i++) {
      const winZ = -3.2 + i * 3.4;
      // Window glass
      const glass = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 2.2), glassMat);
      glass.position.set(-5.97, 2.6, winZ);
      glass.rotation.y = Math.PI / 2;
      scene.add(glass);

      // Window white frame
      const frame = new THREE.Mesh(new THREE.BoxGeometry(0.08, 2.3, 2.5), windowFrameMat);
      frame.position.set(-5.96, 2.6, winZ);
      scene.add(frame);
    }

    // Right Wall with door and cork bulletin board
    const rightWall = new THREE.Mesh(new THREE.PlaneGeometry(18, 5), leftWallMat);
    rightWall.position.set(6, 2.5, 0);
    rightWall.rotation.y = -Math.PI / 2;
    scene.add(rightWall);

    // Classroom door on right wall
    const doorMat = new THREE.MeshStandardMaterial({ color: 0xb57a44, roughness: 0.5 });
    const door = new THREE.Mesh(new THREE.BoxGeometry(0.06, 2.8, 1.3), doorMat);
    door.position.set(5.96, 1.4, -2.5);
    scene.add(door);

    // Cork bulletin board on right wall
    const corkMat = new THREE.MeshStandardMaterial({ color: 0xb88856, roughness: 0.9 });
    const corkBoard = new THREE.Mesh(new THREE.BoxGeometry(0.05, 1.5, 2.8), corkMat);
    corkBoard.position.set(5.96, 2.4, 1.2);
    scene.add(corkBoard);

    // Ceiling
    const ceilingMat = new THREE.MeshStandardMaterial({ color: 0xfbfbfb, roughness: 0.9 });
    const ceiling = new THREE.Mesh(new THREE.PlaneGeometry(16, 18), ceilingMat);
    ceiling.position.set(0, 4.8, -1);
    ceiling.rotation.x = Math.PI / 2;
    scene.add(ceiling);

    // Ceiling fluorescent lights
    const lightFixtureMat = new THREE.MeshBasicMaterial({ color: 0xfffbeb });
    for (let r = 0; r < 3; r++) {
      for (let c = 0; c < 2; c++) {
        const fixture = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.08, 1.8), lightFixtureMat);
        fixture.position.set(-2.5 + c * 5.0, 4.75, -3.5 + r * 3.8);
        scene.add(fixture);
      }
    }

    // 5. Dynamic 3D Blackboard
    const bbCanvas = createBlackboardCanvas();
    blackboardCanvasRef.current = bbCanvas;
    bbCanvas.updateContent(blackboardData);

    const bbTexture = new THREE.CanvasTexture(bbCanvas.canvas);
    bbTexture.minFilter = THREE.LinearFilter;
    bbTexture.magFilter = THREE.LinearFilter;
    blackboardTextureRef.current = bbTexture;

    // Blackboard Frame
    const boardWidth = 6.2;
    const boardHeight = 2.7;
    const frameMat = new THREE.MeshStandardMaterial({ color: 0x5c4033, roughness: 0.6 });
    const boardFrame = new THREE.Mesh(new THREE.BoxGeometry(boardWidth + 0.16, boardHeight + 0.16, 0.08), frameMat);
    boardFrame.position.set(0, 2.6, -5.44);
    boardFrame.castShadow = true;
    scene.add(boardFrame);

    // Chalkboard Face
    const boardMat = new THREE.MeshStandardMaterial({
      map: bbTexture,
      roughness: 0.75,
      metalness: 0.05,
    });
    const blackboardMesh = new THREE.Mesh(new THREE.PlaneGeometry(boardWidth, boardHeight), boardMat);
    blackboardMesh.position.set(0, 2.6, -5.39);
    scene.add(blackboardMesh);

    // Chalk tray & chalk piece
    const tray = new THREE.Mesh(
      new THREE.BoxGeometry(boardWidth, 0.06, 0.16),
      new THREE.MeshStandardMaterial({ color: 0x8b5a2b })
    );
    tray.position.set(0, 1.22, -5.35);
    scene.add(tray);

    // Wall Clock above board
    const clockMat = new THREE.MeshStandardMaterial({ color: 0xf1f5f9 });
    const clock = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.35, 0.06, 24), clockMat);
    clock.rotation.x = Math.PI / 2;
    clock.position.set(0, 4.3, -5.46);
    scene.add(clock);

    // 6. Teacher's Desk & Props
    const teacherDeskMat = new THREE.MeshStandardMaterial({ color: 0x8b5a2b, roughness: 0.6 });
    const teacherDesk = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.85, 1.1), teacherDeskMat);
    teacherDesk.position.set(0, 0.425, -4.2);
    teacherDesk.castShadow = true;
    teacherDesk.receiveShadow = true;
    scene.add(teacherDesk);

    // Bookshelf in corner
    const bookshelfMat = new THREE.MeshStandardMaterial({ color: 0x7c4e28, roughness: 0.7 });
    const bookshelf = new THREE.Mesh(new THREE.BoxGeometry(1.6, 2.6, 0.6), bookshelfMat);
    bookshelf.position.set(-4.8, 1.3, -5.0);
    scene.add(bookshelf);

    // 7. Characters & Student Stations
    // Bob (Teacher)
    const bob = createBobTeacher();
    bob.root.position.set(0, 0, -3.2); // Right in front of teacher desk & board
    bob.root.rotation.y = 0;
    bob.root.traverse((obj) => {
      if ((obj as THREE.Mesh).isMesh) {
        obj.castShadow = true;
        obj.receiveShadow = true;
      }
    });
    scene.add(bob.root);
    bobRigRef.current = bob;

    // Alice Station (Left Front Row, angled slightly inward toward chalkboard)
    const alicePos = new THREE.Vector3(-2.3, 0, -1.1);
    const aliceAngle = 0.16;

    const aliceDesk = createDeskAndChair();
    aliceDesk.position.copy(alicePos);
    aliceDesk.rotation.y = aliceAngle;
    scene.add(aliceDesk);

    const aliceProps = createDeskProps(false);
    aliceProps.position.copy(alicePos);
    aliceProps.rotation.y = aliceAngle;
    scene.add(aliceProps);

    const alice = createAliceStudent();
    alice.root.position.copy(alicePos);
    alice.root.rotation.y = aliceAngle;
    alice.root.traverse((obj) => {
      if ((obj as THREE.Mesh).isMesh) {
        obj.castShadow = true;
        obj.receiveShadow = true;
      }
    });
    scene.add(alice.root);
    aliceRigRef.current = alice;

    // Charlie Station (Right Front Row, angled slightly inward toward chalkboard)
    const charliePos = new THREE.Vector3(2.3, 0, -1.1);
    const charlieAngle = -0.16;

    const charlieDesk = createDeskAndChair();
    charlieDesk.position.copy(charliePos);
    charlieDesk.rotation.y = charlieAngle;
    scene.add(charlieDesk);

    const charlieProps = createDeskProps(false);
    charlieProps.position.copy(charliePos);
    charlieProps.rotation.y = charlieAngle;
    scene.add(charlieProps);

    const charlie = createCharlieStudent();
    charlie.root.position.copy(charliePos);
    charlie.root.rotation.y = charlieAngle;
    charlie.root.traverse((obj) => {
      if ((obj as THREE.Mesh).isMesh) {
        obj.castShadow = true;
        obj.receiveShadow = true;
      }
    });
    scene.add(charlie.root);
    charlieRigRef.current = charlie;

    // Asynchronously check and load user-provided Mixamo FBX or GLB models from /public/avatars/
    const tryLoadCustomAvatar = async (
      name: 'bob' | 'alice' | 'charlie',
      fallbackRig: CharacterRig,
      position: THREE.Vector3,
      rotationY: number,
      isSeated: boolean,
      setRig: (rig: CharacterRig) => void
    ) => {
      const candidates = [`/avatars/${name}.fbx`, `/avatars/${name}.glb`];
      for (const url of candidates) {
        try {
          const res = await fetch(url, { method: 'HEAD' });
          if (res.ok) {
            const isFbx = url.endsWith('.fbx');
            const customRig = isFbx
              ? await loadMixamoFBXAvatar(url, { isSeated, rotationY, targetHeight: isSeated ? 1.45 : 1.75 })
              : await loadGLBAvatar(url, { isSeated, rotationY, targetHeight: isSeated ? 1.45 : 1.75 });
            if (customRig && sceneRef.current) {
              scene.remove(fallbackRig.root);
              customRig.root.position.copy(position);
              customRig.root.rotation.y = rotationY;
              scene.add(customRig.root);
              setRig(customRig);
              break;
            }
          }
        } catch {
          // Keep procedural avatar fallback
        }
      }
    };

    tryLoadCustomAvatar('bob', bob, new THREE.Vector3(0, 0, -3.2), 0, false, (r) => {
      bobRigRef.current = r;
    });
    tryLoadCustomAvatar('alice', alice, alicePos, aliceAngle, true, (r) => {
      aliceRigRef.current = r;
    });
    tryLoadCustomAvatar('charlie', charlie, charliePos, charlieAngle, true, (r) => {
      charlieRigRef.current = r;
    });

    // User's Desk (Center Front Row - User's seat!)
    const userDesk = createDeskAndChair();
    userDesk.position.set(0, 0, 0.2);
    scene.add(userDesk);
    const userProps = createDeskProps(true);
    userProps.position.set(0, 0, 0.2);
    scene.add(userProps);

    // User 3D Speech bubble anchor (projected just in front / above the user's desk)
    const userAnchor = new THREE.Object3D();
    userAnchor.position.set(0, 1.45, 0.0);
    scene.add(userAnchor);
    userAnchorRef.current = userAnchor;

    // Additional background desks to complete the classroom ambience
    const extraDeskPositions: [number, number][] = [
      [-2.3, 1.8],
      [0, 2.4],
      [2.3, 1.8],
      [-2.3, 3.8],
      [2.3, 3.8],
    ];
    extraDeskPositions.forEach(([x, z]) => {
      const d = createDeskAndChair();
      d.position.set(x, 0, z);
      scene.add(d);
    });

    // 9. Interactive Look Around Handlers
    let isMouseDown = false;
    let mouseX = 0;
    let mouseY = 0;

    const onMouseDown = (e: MouseEvent) => {
      isMouseDown = true;
      mouseX = e.clientX;
      mouseY = e.clientY;
      isDraggingRef.current = true;
      setHintDismissed(true);
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!isMouseDown) return;
      const deltaX = e.clientX - mouseX;
      const deltaY = e.clientY - mouseY;
      mouseX = e.clientX;
      mouseY = e.clientY;

      // Subtle natural rotational look
      cameraEulerRef.current.y -= deltaX * 0.003;
      cameraEulerRef.current.x -= deltaY * 0.0025;
      // Clamp vertical look to realistic eye range
      cameraEulerRef.current.x = Math.max(-0.45, Math.min(0.35, cameraEulerRef.current.x));
      // Clamp horizontal look around
      cameraEulerRef.current.y = Math.max(-0.9, Math.min(0.9, cameraEulerRef.current.y));
    };

    const onMouseUp = () => {
      isMouseDown = false;
      isDraggingRef.current = false;
    };

    // Touch support for mobile / tablet
    const onTouchStart = (e: TouchEvent) => {
      if (e.touches.length === 1) {
        isMouseDown = true;
        mouseX = e.touches[0].clientX;
        mouseY = e.touches[0].clientY;
        setHintDismissed(true);
      }
    };

    const onTouchMove = (e: TouchEvent) => {
      if (!isMouseDown || e.touches.length !== 1) return;
      const deltaX = e.touches[0].clientX - mouseX;
      const deltaY = e.touches[0].clientY - mouseY;
      mouseX = e.touches[0].clientX;
      mouseY = e.touches[0].clientY;
      cameraEulerRef.current.y -= deltaX * 0.0035;
      cameraEulerRef.current.x -= deltaY * 0.003;
      cameraEulerRef.current.x = Math.max(-0.45, Math.min(0.35, cameraEulerRef.current.x));
      cameraEulerRef.current.y = Math.max(-0.9, Math.min(0.9, cameraEulerRef.current.y));
    };

    const onTouchEnd = () => {
      isMouseDown = false;
    };

    const dom = renderer.domElement;
    dom.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    dom.addEventListener('touchstart', onTouchStart, { passive: true });
    dom.addEventListener('touchmove', onTouchMove, { passive: true });
    dom.addEventListener('touchend', onTouchEnd);

    // 10. Animation Loop
    let animationFrameId: number;
    const clockTimer = new THREE.Clock();

    const animate = () => {
      animationFrameId = requestAnimationFrame(animate);
      const elapsedTime = clockTimer.getElapsedTime();

      // Update character procedural rigs
      if (bobRigRef.current) bobRigRef.current.updateAnimation(elapsedTime);
      if (aliceRigRef.current) aliceRigRef.current.updateAnimation(elapsedTime);
      if (charlieRigRef.current) charlieRigRef.current.updateAnimation(elapsedTime);

      // Smooth camera interpolation towards target position
      camera.position.lerp(targetCameraPosRef.current, 0.06);

      // Combine target look and user mouse look
      const lookRotation = new THREE.Quaternion().setFromEuler(cameraEulerRef.current);
      const forwardDir = new THREE.Vector3(0, 0, -1).applyQuaternion(lookRotation);
      const currentLookTarget = camera.position.clone().add(forwardDir.multiplyScalar(4.5));
      camera.lookAt(currentLookTarget);

      renderer.render(scene, camera);

      // Compute screen projections for speech bubbles
      const w = container.clientWidth;
      const h = container.clientHeight;
      const coords: Record<SpeakerId, ScreenCoord> = {
        bob: bobRigRef.current
          ? projectToScreen(bobRigRef.current.speechAnchor, camera, w, h)
          : { x: 0, y: 0, visible: false },
        alice: aliceRigRef.current
          ? projectToScreen(aliceRigRef.current.speechAnchor, camera, w, h)
          : { x: 0, y: 0, visible: false },
        charlie: charlieRigRef.current
          ? projectToScreen(charlieRigRef.current.speechAnchor, camera, w, h)
          : { x: 0, y: 0, visible: false },
        user: userAnchorRef.current
          ? projectToScreen(userAnchorRef.current, camera, w, h)
          : { x: 0, y: 0, visible: false },
      };
      onCoordinatesUpdate(coords);
    };

    animate();

    // Resize observer
    const resizeObserver = new ResizeObserver(() => {
      if (!container || !rendererRef.current || !cameraRef.current) return;
      const nw = container.clientWidth;
      const nh = container.clientHeight;
      cameraRef.current.aspect = nw / nh;
      cameraRef.current.updateProjectionMatrix();
      rendererRef.current.setSize(nw, nh);
    });
    resizeObserver.observe(container);

    // Cleanup
    return () => {
      cancelAnimationFrame(animationFrameId);
      resizeObserver.disconnect();
      dom.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      dom.removeEventListener('touchstart', onTouchStart);
      dom.removeEventListener('touchmove', onTouchMove);
      dom.removeEventListener('touchend', onTouchEnd);

      if (rendererRef.current && rendererRef.current.domElement.parentNode) {
        rendererRef.current.domElement.parentNode.removeChild(rendererRef.current.domElement);
      }
      rendererRef.current?.dispose();
    };
  }, [projectToScreen, onCoordinatesUpdate]);

  return (
    <div
      id="classroom-3d-viewport"
      ref={containerRef}
      className="relative w-full h-full select-none cursor-grab active:cursor-grabbing overflow-hidden bg-slate-900"
    >
      {/* Onscreen look instruction badge */}
      {!hintDismissed && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 pointer-events-none z-20 transition-opacity duration-500">
          <div className="px-5 py-2 rounded-full bg-black/60 backdrop-blur-md border border-white/10 text-white/90 text-xs sm:text-sm font-medium shadow-lg tracking-wide flex items-center gap-2">
            <span>Click & drag to look around classroom • ESC or controls to change view</span>
          </div>
        </div>
      )}
    </div>
  );
};
