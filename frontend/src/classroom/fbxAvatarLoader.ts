import * as THREE from 'three';
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js';
import { CharacterRig } from './proceduralCharacters';

/**
 * Utility to load Mixamo FBX Binary (.fbx) character models.
 * Mixamo models typically have standard 'mixamorig' bone naming.
 */
export async function loadMixamoFBXAvatar(
  url: string,
  options: {
    targetHeight?: number;
    rotationY?: number;
    isSeated?: boolean;
  } = {}
): Promise<CharacterRig | null> {
  const loader = new FBXLoader();
  const { targetHeight = 1.6, rotationY = 0, isSeated = false } = options;

  try {
    const fbx = await loader.loadAsync(url);

    // Enable shadows on all child meshes
    fbx.traverse((child) => {
      if ((child as THREE.Mesh).isMesh) {
        child.castShadow = true;
        child.receiveShadow = true;
      }
    });

    // Compute bounding box and normalize scale to match target human height
    const box = new THREE.Box3().setFromObject(fbx);
    const size = new THREE.Vector3();
    box.getSize(size);

    if (size.y > 0) {
      const scale = targetHeight / size.y;
      fbx.scale.set(scale, scale, scale);
    }

    const root = new THREE.Group();
    root.add(fbx);

    // Identify standard Mixamo bones for head tracking and gesture controls
    let headBone: THREE.Bone | THREE.Object3D | null = null;
    let rightArmBone: THREE.Bone | THREE.Object3D | null = null;
    let leftArmBone: THREE.Bone | THREE.Object3D | null = null;
    let rightForeArmBone: THREE.Bone | THREE.Object3D | null = null;
    let leftUpLeg: THREE.Bone | THREE.Object3D | null = null;
    let rightUpLeg: THREE.Bone | THREE.Object3D | null = null;
    let leftLeg: THREE.Bone | THREE.Object3D | null = null;
    let rightLeg: THREE.Bone | THREE.Object3D | null = null;

    fbx.traverse((child) => {
      const name = child.name.toLowerCase();
      if (!headBone && (name.includes('head') || name.includes('neck'))) {
        headBone = child;
      }
      if (!rightArmBone && (name.includes('rightarm') || name.includes('rightshoulder') || name.includes('arm_r'))) {
        rightArmBone = child;
      }
      if (!rightForeArmBone && (name.includes('rightforearm') || name.includes('forearm_r'))) {
        rightForeArmBone = child;
      }
      if (!leftArmBone && (name.includes('leftarm') || name.includes('leftshoulder') || name.includes('arm_l'))) {
        leftArmBone = child;
      }
      if (!leftUpLeg && (name.includes('leftupleg') || name.includes('thigh_l') || name.includes('upleg_l'))) {
        leftUpLeg = child;
      }
      if (!rightUpLeg && (name.includes('rightupleg') || name.includes('thigh_r') || name.includes('upleg_r'))) {
        rightUpLeg = child;
      }
      if (!leftLeg && (name.includes('leftleg') || name.includes('shin_l') || name.includes('calf_l'))) {
        leftLeg = child;
      }
      if (!rightLeg && (name.includes('rightleg') || name.includes('shin_r') || name.includes('calf_r'))) {
        rightLeg = child;
      }
    });

    // If seated and model is in default standing T-pose/A-pose without an animation,
    // position hips to seat on the chair and fold legs forward
    if (isSeated) {
      fbx.position.set(0, 0.46, 0.62);

      // If no baked animations, bend legs to sit comfortably
      if (fbx.animations.length === 0) {
        if (leftUpLeg) leftUpLeg.rotation.x = -Math.PI / 2;
        if (rightUpLeg) rightUpLeg.rotation.x = -Math.PI / 2;
        if (leftLeg) leftLeg.rotation.x = Math.PI / 2;
        if (rightLeg) rightLeg.rotation.x = Math.PI / 2;
      }
    }

    if (rotationY !== 0) {
      fbx.rotation.y = rotationY;
    }

    // Set speech bubble anchor
    const speechAnchor = new THREE.Object3D();
    speechAnchor.position.set(0, isSeated ? 1.72 : 2.2, isSeated ? 0.56 : 0);
    root.add(speechAnchor);

    // Setup animation mixer if animations exist
    const mixer = fbx.animations.length > 0 ? new THREE.AnimationMixer(fbx) : null;
    if (mixer && fbx.animations[0]) {
      const action = mixer.clipAction(fbx.animations[0]);
      action.play();
    }

    const clock = new THREE.Clock();

    const dummyHead = (headBone as unknown as THREE.Group) || new THREE.Group();
    const dummyRArm = (rightArmBone as unknown as THREE.Group) || new THREE.Group();
    const dummyLArm = (leftArmBone as unknown as THREE.Group) || new THREE.Group();

    return {
      root,
      head: dummyHead,
      rightArm: dummyRArm,
      leftArm: dummyLArm,
      speechAnchor,
      setEmotion: () => {},
      setGesture: (gesture: string) => {
        if (gesture === 'raise_hand' && rightArmBone) {
          rightArmBone.rotation.x = -1.2;
          rightArmBone.rotation.z = -0.3;
        } else if (gesture === 'point_chalkboard' && rightArmBone) {
          rightArmBone.rotation.x = -1.3;
          rightArmBone.rotation.y = 0.4;
        } else if (rightArmBone && fbx.animations.length === 0) {
          rightArmBone.rotation.set(0, 0, 0);
        }
      },
      updateAnimation: (time: number) => {
        if (mixer) {
          mixer.update(clock.getDelta());
        } else {
          // Idle breathing
          fbx.position.y = (isSeated ? 0.46 : 0) + Math.sin(time * 2.2) * 0.008;
        }
      },
    };
  } catch (error) {
    console.warn(`Could not load FBX avatar from ${url}:`, error);
    return null;
  }
}
