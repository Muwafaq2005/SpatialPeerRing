import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { CharacterRig } from './proceduralCharacters';

/**
 * Utility to load external GLB / GLTF 3D models for classroom characters
 * (e.g., from Ready Player Me, Mixamo, Sketchfab, or custom Blender models).
 *
 * If a GLB model is placed in /public/avatars/alice.glb or /public/avatars/charlie.glb,
 * or provided via URL, this loader will instantiate it and bind it to the CharacterRig interface.
 */
export async function loadGLBAvatar(
  url: string,
  options: {
    targetHeight?: number;
    rotationY?: number;
    isSeated?: boolean;
  } = {}
): Promise<CharacterRig | null> {
  const loader = new GLTFLoader();
  const { targetHeight = 1.6, rotationY = 0, isSeated = false } = options;

  try {
    const gltf = await loader.loadAsync(url);
    const model = gltf.scene;

    // Enable shadows
    model.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        child.castShadow = true;
        child.receiveShadow = true;
      }
    });

    // Compute bounding box to scale to target human height
    const box = new THREE.Box3().setFromObject(model);
    const size = new THREE.Vector3();
    box.getSize(size);

    if (size.y > 0) {
      const scale = targetHeight / size.y;
      model.scale.set(scale, scale, scale);
    }

    const root = new THREE.Group();
    root.add(model);

    // If seated, position model to align with student chair
    if (isSeated) {
      model.position.set(0, 0.46, 0.62);
    }

    // Try to find head or spine bones for speech anchor / head movement
    let headBone: THREE.Object3D | null = null;
    let rightArmBone: THREE.Object3D | null = null;
    let leftArmBone: THREE.Object3D | null = null;

    model.traverse((child) => {
      const lower = child.name.toLowerCase();
      if (!headBone && (lower.includes('head') || lower.includes('neck'))) {
        headBone = child;
      }
      if (!rightArmBone && (lower.includes('rightarm') || lower.includes('arm_r') || lower.includes('rightshoulder'))) {
        rightArmBone = child;
      }
      if (!leftArmBone && (lower.includes('leftarm') || lower.includes('arm_l') || lower.includes('leftshoulder'))) {
        leftArmBone = child;
      }
    });

    const dummyHead = (headBone as unknown as THREE.Group) || new THREE.Group();
    const dummyRArm = (rightArmBone as unknown as THREE.Group) || new THREE.Group();
    const dummyLArm = (leftArmBone as unknown as THREE.Group) || new THREE.Group();

    const speechAnchor = new THREE.Object3D();
    speechAnchor.position.set(0, isSeated ? 1.7 : 2.1, isSeated ? 0.56 : 0);
    root.add(speechAnchor);

    // Animation mixer if animations are included in GLB
    const mixer = gltf.animations.length > 0 ? new THREE.AnimationMixer(model) : null;
    if (mixer && gltf.animations[0]) {
      const action = mixer.clipAction(gltf.animations[0]);
      action.play();
    }

    let clock = new THREE.Clock();

    return {
      root,
      head: dummyHead,
      rightArm: dummyRArm,
      leftArm: dummyLArm,
      speechAnchor,
      setEmotion: () => {},
      setGesture: () => {},
      updateAnimation: (time: number) => {
        if (mixer) {
          mixer.update(clock.getDelta());
        } else {
          // Subtle idle breathing
          model.position.y = (isSeated ? 0.46 : 0) + Math.sin(time * 2) * 0.01;
        }
      },
    };
  } catch (error) {
    console.warn(`Could not load GLB avatar from ${url}:`, error);
    return null;
  }
}
