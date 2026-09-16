import * as THREE from 'three';

export interface CharacterRig {
  root: THREE.Group;
  head: THREE.Group;
  rightArm: THREE.Group;
  leftArm: THREE.Group;
  speechAnchor: THREE.Object3D;
  setEmotion: (emotion: string) => void;
  setGesture: (gesture: string) => void;
  updateAnimation: (time: number) => void;
}

/**
 * Helper to build high-polish stylized eyes with pupils and double specular catchlights
 */
function createStylizedEye(
  irisColor: number,
  isLeft: boolean
): THREE.Group {
  const eyeGroup = new THREE.Group();

  // White Sclera
  const scleraMat = new THREE.MeshStandardMaterial({
    color: 0xfdfdfd,
    roughness: 0.2,
  });
  const sclera = new THREE.Mesh(new THREE.SphereGeometry(0.038, 16, 12), scleraMat);
  sclera.scale.set(1.0, 0.88, 0.45);
  eyeGroup.add(sclera);

  // Colored Iris
  const irisMat = new THREE.MeshStandardMaterial({
    color: irisColor,
    roughness: 0.3,
  });
  const iris = new THREE.Mesh(new THREE.SphereGeometry(0.024, 16, 12), irisMat);
  iris.scale.set(1.0, 1.0, 0.35);
  iris.position.set(0, 0, -0.012);
  eyeGroup.add(iris);

  // Deep Pupil
  const pupilMat = new THREE.MeshBasicMaterial({ color: 0x09090b });
  const pupil = new THREE.Mesh(new THREE.SphereGeometry(0.014, 12, 10), pupilMat);
  pupil.scale.set(1.0, 1.0, 0.35);
  pupil.position.set(0, 0, -0.018);
  eyeGroup.add(pupil);

  // Specular Catchlights (Gives life and expression to the eyes!)
  const sparkleMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const sparkle1 = new THREE.Mesh(new THREE.SphereGeometry(0.006, 8, 8), sparkleMat);
  sparkle1.position.set(isLeft ? -0.007 : 0.007, 0.008, -0.022);
  eyeGroup.add(sparkle1);

  const sparkle2 = new THREE.Mesh(new THREE.SphereGeometry(0.0035, 6, 6), sparkleMat);
  sparkle2.position.set(isLeft ? 0.006 : -0.006, -0.006, -0.022);
  eyeGroup.add(sparkle2);

  // Upper eyelid / eyelash line
  const lashMat = new THREE.MeshBasicMaterial({ color: 0x271810 });
  const lash = new THREE.Mesh(new THREE.TorusGeometry(0.032, 0.0045, 6, 12, Math.PI * 0.9), lashMat);
  lash.rotation.x = Math.PI * 0.15;
  lash.rotation.z = Math.PI * 0.05 * (isLeft ? 1 : -1);
  lash.position.set(0, 0.022, -0.014);
  eyeGroup.add(lash);

  return eyeGroup;
}

/**
 * Creates Bob the AI Tutor/Teacher standing near the chalkboard
 */
export function createBobTeacher(): CharacterRig {
  const root = new THREE.Group();
  root.name = 'bob_teacher';

  // Materials
  const skinMat = new THREE.MeshStandardMaterial({ color: 0xf5d3be, roughness: 0.55 });
  const hairMat = new THREE.MeshStandardMaterial({ color: 0x3d2c22, roughness: 0.8 });
  const blazerMat = new THREE.MeshStandardMaterial({ color: 0x1e3a5f, roughness: 0.7 }); // Scholarly navy blazer
  const vestMat = new THREE.MeshStandardMaterial({ color: 0x475569, roughness: 0.8 });
  const shirtMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.45 });
  const tieMat = new THREE.MeshStandardMaterial({ color: 0x991b1b, roughness: 0.5 }); // Deep burgundy tie
  const pantsMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.75 });
  const shoeMat = new THREE.MeshStandardMaterial({ color: 0x1c1917, roughness: 0.35 });
  const glassesMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, metalness: 0.85, roughness: 0.2 });
  const chalkMat = new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.9 });

  // 1. Torso & Upper Body
  const torsoGroup = new THREE.Group();
  torsoGroup.position.set(0, 1.36, 0);

  // Blazer / Chest (smooth capsule shape)
  const blazer = new THREE.Mesh(new THREE.CapsuleGeometry(0.24, 0.44, 10, 16), blazerMat);
  blazer.scale.set(1.15, 1.0, 0.8);
  blazer.castShadow = true;
  torsoGroup.add(blazer);

  // Shirt & Tie V-neck cutout
  const shirtInset = new THREE.Mesh(new THREE.PlaneGeometry(0.16, 0.32), shirtMat);
  shirtInset.position.set(0, 0.1, 0.2);
  torsoGroup.add(shirtInset);

  const tie = new THREE.Mesh(new THREE.BoxGeometry(0.065, 0.28, 0.02), tieMat);
  tie.position.set(0, 0.08, 0.21);
  torsoGroup.add(tie);

  const collar = new THREE.Mesh(new THREE.BoxGeometry(0.22, 0.08, 0.04), shirtMat);
  collar.position.set(0, 0.25, 0.18);
  torsoGroup.add(collar);

  // Pocket square
  const pocketSquare = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.03, 0.015), shirtMat);
  pocketSquare.position.set(-0.16, 0.14, 0.2);
  pocketSquare.rotation.z = -0.15;
  torsoGroup.add(pocketSquare);

  // 2. Neck & Head
  const head = new THREE.Group();
  head.position.set(0, 1.88, 0);

  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.085, 0.12, 16), skinMat);
  neck.position.set(0, -0.1, 0);
  head.add(neck);

  // Face
  const face = new THREE.Mesh(new THREE.SphereGeometry(0.18, 24, 20), skinMat);
  face.scale.set(0.95, 1.08, 0.95);
  face.castShadow = true;
  head.add(face);

  // Stylized Hair (curved sculpted volume with clean side-part)
  const hairTop = new THREE.Mesh(new THREE.SphereGeometry(0.19, 20, 16), hairMat);
  hairTop.scale.set(0.98, 0.8, 1.02);
  hairTop.position.set(0, 0.1, -0.02);
  head.add(hairTop);

  const hairSwoop = new THREE.Mesh(new THREE.CapsuleGeometry(0.06, 0.16, 8, 12), hairMat);
  hairSwoop.rotation.z = Math.PI * 0.35;
  hairSwoop.position.set(0.06, 0.15, 0.12);
  head.add(hairSwoop);

  // Eyes (Bob faces +Z towards the students)
  const leftEye = createStylizedEye(0x3b2f2f, true);
  leftEye.rotation.y = Math.PI; // Face +Z
  leftEye.position.set(-0.068, 0.02, 0.165);
  head.add(leftEye);

  const rightEye = createStylizedEye(0x3b2f2f, false);
  rightEye.rotation.y = Math.PI;
  rightEye.position.set(0.068, 0.02, 0.165);
  head.add(rightEye);

  // Glasses
  const glassesFrameGeom = new THREE.TorusGeometry(0.05, 0.008, 8, 16);
  const gL = new THREE.Mesh(glassesFrameGeom, glassesMat);
  gL.position.set(-0.068, 0.02, 0.175);
  head.add(gL);

  const gR = new THREE.Mesh(glassesFrameGeom, glassesMat);
  gR.position.set(0.068, 0.02, 0.175);
  head.add(gR);

  const bridge = new THREE.Mesh(new THREE.BoxGeometry(0.045, 0.01, 0.01), glassesMat);
  bridge.position.set(0, 0.02, 0.175);
  head.add(bridge);

  // Eyebrows
  const browMat = new THREE.MeshBasicMaterial({ color: 0x271810 });
  const bL = new THREE.Mesh(new THREE.BoxGeometry(0.065, 0.012, 0.015), browMat);
  bL.position.set(-0.068, 0.075, 0.165);
  bL.rotation.z = 0.05;
  head.add(bL);

  const bR = new THREE.Mesh(new THREE.BoxGeometry(0.065, 0.012, 0.015), browMat);
  bR.position.set(0.068, 0.075, 0.165);
  bR.rotation.z = -0.05;
  head.add(bR);

  // Friendly smile
  const mouthMat = new THREE.MeshBasicMaterial({ color: 0x9f1239 });
  const mouth = new THREE.Mesh(new THREE.TorusGeometry(0.03, 0.006, 6, 12, Math.PI * 0.8), mouthMat);
  mouth.rotation.x = Math.PI * 0.1;
  mouth.rotation.z = Math.PI * 0.1;
  mouth.position.set(0, -0.07, 0.165);
  head.add(mouth);

  // 3. Arms
  // Right Arm (Pointing / Chalk arm)
  const rightArm = new THREE.Group();
  rightArm.position.set(0.32, 1.58, 0);

  const upperArmGeom = new THREE.CapsuleGeometry(0.065, 0.28, 8, 12);
  const rUpper = new THREE.Mesh(upperArmGeom, blazerMat);
  rUpper.position.y = -0.15;
  rightArm.add(rUpper);

  const rForearmGroup = new THREE.Group();
  rForearmGroup.position.set(0, -0.32, 0);
  const rForearm = new THREE.Mesh(new THREE.CapsuleGeometry(0.055, 0.26, 8, 12), blazerMat);
  rForearm.position.y = -0.13;
  rForearmGroup.add(rForearm);

  // Hand with chalk
  const rHand = new THREE.Mesh(new THREE.SphereGeometry(0.045, 12, 10), skinMat);
  rHand.position.set(0, -0.28, 0.02);
  rForearmGroup.add(rHand);

  const chalk = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.1, 8), chalkMat);
  chalk.rotation.x = Math.PI / 3;
  chalk.position.set(0, -0.29, 0.06);
  rForearmGroup.add(chalk);

  rightArm.add(rForearmGroup);

  // Left Arm (Scholarly relaxed)
  const leftArm = new THREE.Group();
  leftArm.position.set(-0.32, 1.58, 0);

  const lUpper = new THREE.Mesh(upperArmGeom, blazerMat);
  lUpper.position.y = -0.15;
  leftArm.add(lUpper);

  const lForearmGroup = new THREE.Group();
  lForearmGroup.position.set(0, -0.32, 0);
  const lForearm = new THREE.Mesh(new THREE.CapsuleGeometry(0.055, 0.26, 8, 12), blazerMat);
  lForearm.position.y = -0.13;
  lForearmGroup.add(lForearm);

  const lHand = new THREE.Mesh(new THREE.SphereGeometry(0.045, 12, 10), skinMat);
  lHand.position.set(0, -0.28, 0.02);
  lForearmGroup.add(lHand);

  leftArm.add(lForearmGroup);

  // 4. Legs & Shoes
  const legGeom = new THREE.CapsuleGeometry(0.085, 0.72, 8, 12);
  const leftLeg = new THREE.Mesh(legGeom, pantsMat);
  leftLeg.position.set(-0.14, 0.54, 0);
  leftLeg.castShadow = true;
  root.add(leftLeg);

  const rightLeg = new THREE.Mesh(legGeom, pantsMat);
  rightLeg.position.set(0.14, 0.54, 0);
  rightLeg.castShadow = true;
  root.add(rightLeg);

  // Polished shoes
  const shoeGeom = new THREE.BoxGeometry(0.13, 0.1, 0.26);
  const leftShoe = new THREE.Mesh(shoeGeom, shoeMat);
  leftShoe.position.set(-0.14, 0.05, 0.05);
  root.add(leftShoe);

  const rightShoe = new THREE.Mesh(shoeGeom, shoeMat);
  rightShoe.position.set(0.14, 0.05, 0.05);
  root.add(rightShoe);

  root.add(torsoGroup);
  root.add(head);
  root.add(rightArm);
  root.add(leftArm);

  const speechAnchor = new THREE.Object3D();
  speechAnchor.position.set(0, 2.32, 0);
  root.add(speechAnchor);

  let currentGesture = 'idle';

  return {
    root,
    head,
    rightArm,
    leftArm,
    speechAnchor,
    setEmotion: () => {},
    setGesture: (g: string) => {
      currentGesture = g;
    },
    updateAnimation: (time: number) => {
      torsoGroup.position.y = 1.36 + Math.sin(time * 2.2) * 0.012;
      head.position.y = 1.88 + Math.sin(time * 2.2) * 0.012;

      if (currentGesture === 'point_chalkboard') {
        rightArm.rotation.x = -1.25 + Math.sin(time * 3) * 0.08;
        rightArm.rotation.z = -0.35;
        rightArm.rotation.y = 0.45;
        head.rotation.y = 0.2 + Math.sin(time * 1.5) * 0.08;
        leftArm.rotation.x = Math.sin(time * 1.5) * 0.06;
      } else if (currentGesture === 'explaining') {
        rightArm.rotation.x = -0.65 + Math.sin(time * 2.5) * 0.12;
        rightArm.rotation.z = -0.25;
        rightArm.rotation.y = 0.1;
        leftArm.rotation.x = -0.55 + Math.cos(time * 2.5) * 0.12;
        leftArm.rotation.z = 0.25;
        head.rotation.y = Math.sin(time * 1.4) * 0.15;
      } else {
        rightArm.rotation.x = Math.sin(time * 1.6) * 0.06;
        rightArm.rotation.z = -0.08;
        rightArm.rotation.y = 0;
        leftArm.rotation.x = -Math.sin(time * 1.6) * 0.06;
        leftArm.rotation.z = 0.08;
        head.rotation.y = Math.sin(time * 0.9) * 0.06;
      }
    },
  };
}

/**
 * Creates Alice the AI Student seated comfortably at her desk.
 *
 * Seating Alignment:
 * - Chair seat is at y = 0.46, z = 0.65.
 * - Alice's pelvis sits at y = 0.50, z = 0.62.
 * - Thighs extend forward toward -Z (from z=0.62 to knees at z=0.28).
 * - Shins drop from knees z=0.28 down to floor at y=0.06.
 * - Torso sits at z=0.60, head at z=0.56, y=1.28.
 * - Arms rest smoothly on the desk top (y=0.775, z=0.18).
 * - Face, eyes, and expressions face -Z toward the teacher & blackboard.
 */
export function createAliceStudent(): CharacterRig {
  const root = new THREE.Group();
  root.name = 'alice_student';

  // Materials
  const skinMat = new THREE.MeshStandardMaterial({ color: 0xfce5d8, roughness: 0.5 });
  const hairMat = new THREE.MeshStandardMaterial({ color: 0x3d2012, roughness: 0.75 }); // Warm brunette / chestnut
  const sweaterMat = new THREE.MeshStandardMaterial({ color: 0xa89382, roughness: 0.85 }); // Chic heather knit sweater
  const collarMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.5 }); // Crisp white shirt collar
  const pantsMat = new THREE.MeshStandardMaterial({ color: 0x273549, roughness: 0.8 }); // Navy tailored slacks
  const loaferMat = new THREE.MeshStandardMaterial({ color: 0x2d1810, roughness: 0.35 });
  const glassesMat = new THREE.MeshStandardMaterial({ color: 0xd97706, metalness: 0.9, roughness: 0.2 }); // Elegant gold wireframes
  const clipMat = new THREE.MeshStandardMaterial({ color: 0xf59e0b, metalness: 0.85, roughness: 0.25 }); // Gold hairpin

  // 1. Seated Pelvis & Legs (Sitting on chair seat at z=0.65, y=0.46)
  const pelvis = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.16, 0.24), pantsMat);
  pelvis.position.set(0, 0.51, 0.62);
  pelvis.castShadow = true;
  root.add(pelvis);

  // Thighs extending forward along -Z toward desk
  const thighGeom = new THREE.CapsuleGeometry(0.075, 0.26, 8, 12);
  const leftThigh = new THREE.Mesh(thighGeom, pantsMat);
  leftThigh.rotation.x = Math.PI / 2;
  leftThigh.position.set(-0.11, 0.51, 0.44);
  root.add(leftThigh);

  const rightThigh = new THREE.Mesh(thighGeom, pantsMat);
  rightThigh.rotation.x = Math.PI / 2;
  rightThigh.position.set(0.11, 0.51, 0.44);
  root.add(rightThigh);

  // Shins dropping down along -Y from knees (z=0.28) to floor
  const shinGeom = new THREE.CapsuleGeometry(0.065, 0.34, 8, 12);
  const leftShin = new THREE.Mesh(shinGeom, pantsMat);
  leftShin.position.set(-0.11, 0.26, 0.28);
  root.add(leftShin);

  const rightShin = new THREE.Mesh(shinGeom, pantsMat);
  rightShin.position.set(0.11, 0.26, 0.28);
  root.add(rightShin);

  // Loafers / Shoes sitting on floor
  const shoeGeom = new THREE.BoxGeometry(0.11, 0.08, 0.2);
  const leftShoe = new THREE.Mesh(shoeGeom, loaferMat);
  leftShoe.position.set(-0.11, 0.04, 0.22);
  root.add(leftShoe);

  const rightShoe = new THREE.Mesh(shoeGeom, loaferMat);
  rightShoe.position.set(0.11, 0.04, 0.22);
  root.add(rightShoe);

  // 2. Torso (Sweater)
  const torsoGroup = new THREE.Group();
  torsoGroup.position.set(0, 0.76, 0.60);

  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.18, 0.32, 8, 16), sweaterMat);
  torso.scale.set(1.1, 1.0, 0.8);
  torso.castShadow = true;
  torsoGroup.add(torso);

  // Ribbed Turtleneck / Shirt collar
  const ribNeck = new THREE.Mesh(new THREE.CylinderGeometry(0.08, 0.09, 0.09, 16), collarMat);
  ribNeck.position.set(0, 0.24, 0);
  torsoGroup.add(ribNeck);

  root.add(torsoGroup);

  // 3. Head & Beautiful Hair
  const head = new THREE.Group();
  head.position.set(0, 1.25, 0.56);

  // Soft contoured face
  const face = new THREE.Mesh(new THREE.SphereGeometry(0.165, 24, 20), skinMat);
  face.scale.set(0.95, 1.05, 0.95);
  face.castShadow = true;
  head.add(face);

  // Stylized Brunette Bob Haircut
  // Hair cap & back volume
  const hairBack = new THREE.Mesh(new THREE.SphereGeometry(0.178, 20, 16), hairMat);
  hairBack.scale.set(0.98, 0.95, 1.05);
  hairBack.position.set(0, 0.05, 0.02);
  head.add(hairBack);

  // Front bangs swept across forehead
  const bangs = new THREE.Mesh(new THREE.CapsuleGeometry(0.05, 0.16, 8, 12), hairMat);
  bangs.rotation.z = Math.PI * 0.42;
  bangs.rotation.x = Math.PI * 0.15;
  bangs.position.set(0.02, 0.12, -0.11);
  head.add(bangs);

  // Left & Right Bob strands framing the face
  const strandL = new THREE.Mesh(new THREE.CapsuleGeometry(0.045, 0.24, 8, 12), hairMat);
  strandL.position.set(-0.14, -0.04, -0.04);
  head.add(strandL);

  const strandR = new THREE.Mesh(new THREE.CapsuleGeometry(0.045, 0.24, 8, 12), hairMat);
  strandR.position.set(0.14, -0.04, -0.04);
  head.add(strandR);

  // Gold hairpin clip
  const clip = new THREE.Mesh(new THREE.BoxGeometry(0.012, 0.045, 0.08), clipMat);
  clip.position.set(0.15, 0.09, -0.07);
  clip.rotation.x = -0.3;
  head.add(clip);

  // Cute Ears
  const earGeom = new THREE.SphereGeometry(0.035, 10, 8);
  const earL = new THREE.Mesh(earGeom, skinMat);
  earL.scale.set(0.5, 1.0, 0.8);
  earL.position.set(-0.16, 0, -0.01);
  head.add(earL);

  const earR = new THREE.Mesh(earGeom, skinMat);
  earR.scale.set(0.5, 1.0, 0.8);
  earR.position.set(0.16, 0, -0.01);
  head.add(earR);

  // Expressive Eyes (Facing -Z toward desk & board!)
  const leftEye = createStylizedEye(0x78350f, true); // Warm amber / hazel
  leftEye.position.set(-0.062, 0.015, -0.145);
  head.add(leftEye);

  const rightEye = createStylizedEye(0x78350f, false);
  rightEye.position.set(0.062, 0.015, -0.145);
  head.add(rightEye);

  // Fine Gold Glasses
  const glassesFrameGeom = new THREE.TorusGeometry(0.044, 0.0055, 8, 16);
  const gL = new THREE.Mesh(glassesFrameGeom, glassesMat);
  gL.position.set(-0.062, 0.015, -0.155);
  head.add(gL);

  const gR = new THREE.Mesh(glassesFrameGeom, glassesMat);
  gR.position.set(0.062, 0.015, -0.155);
  head.add(gR);

  const gBridge = new THREE.Mesh(new THREE.BoxGeometry(0.038, 0.007, 0.007), glassesMat);
  gBridge.position.set(0, 0.015, -0.155);
  head.add(gBridge);

  // Eyebrows
  const browMat = new THREE.MeshBasicMaterial({ color: 0x3d2012 });
  const bL = new THREE.Mesh(new THREE.BoxGeometry(0.055, 0.009, 0.012), browMat);
  bL.position.set(-0.062, 0.068, -0.145);
  bL.rotation.z = -0.04;
  head.add(bL);

  const bR = new THREE.Mesh(new THREE.BoxGeometry(0.055, 0.009, 0.012), browMat);
  bR.position.set(0.062, 0.068, -0.145);
  bR.rotation.z = 0.04;
  head.add(bR);

  // Nose tip
  const nose = new THREE.Mesh(new THREE.SphereGeometry(0.016, 8, 8), skinMat);
  nose.position.set(0, -0.018, -0.165);
  head.add(nose);

  // Sweet smile
  const mouthMat = new THREE.MeshBasicMaterial({ color: 0xd9777f });
  const mouth = new THREE.Mesh(new THREE.TorusGeometry(0.024, 0.005, 6, 12, Math.PI * 0.8), mouthMat);
  mouth.rotation.x = -Math.PI * 0.1;
  mouth.position.set(0, -0.062, -0.15);
  head.add(mouth);

  root.add(head);

  // 4. Arms & Hands (Resting comfortably on the desk top at y=0.775, z=0.18)
  const armGeom = new THREE.CapsuleGeometry(0.055, 0.24, 8, 12);
  const handGeom = new THREE.SphereGeometry(0.038, 10, 8);

  // Right Arm (Writing / Hand-raising arm)
  const rightArm = new THREE.Group();
  rightArm.position.set(0.24, 0.98, 0.58);

  const rUpper = new THREE.Mesh(armGeom, sweaterMat);
  rUpper.position.set(0, -0.12, -0.08);
  rUpper.rotation.x = -0.6;
  rightArm.add(rUpper);

  const rForearmGroup = new THREE.Group();
  rForearmGroup.position.set(0, -0.22, -0.16);

  const rForearm = new THREE.Mesh(armGeom, sweaterMat);
  rForearm.position.set(0, 0, -0.12);
  rForearm.rotation.x = -1.35;
  rForearmGroup.add(rForearm);

  const rHand = new THREE.Mesh(handGeom, skinMat);
  rHand.scale.set(1.0, 0.6, 1.2);
  rHand.position.set(0, 0.01, -0.25);
  rForearmGroup.add(rHand);

  // Pen held in right hand
  const penMat = new THREE.MeshStandardMaterial({ color: 0x2563eb });
  const pen = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.005, 0.12, 8), penMat);
  pen.rotation.x = Math.PI / 4;
  pen.position.set(0.01, 0.03, -0.26);
  rForearmGroup.add(pen);

  rightArm.add(rForearmGroup);
  root.add(rightArm);

  // Left Arm (Resting on desk)
  const leftArm = new THREE.Group();
  leftArm.position.set(-0.24, 0.98, 0.58);

  const lUpper = new THREE.Mesh(armGeom, sweaterMat);
  lUpper.position.set(0, -0.12, -0.08);
  lUpper.rotation.x = -0.6;
  leftArm.add(lUpper);

  const lForearmGroup = new THREE.Group();
  lForearmGroup.position.set(0, -0.22, -0.16);

  const lForearm = new THREE.Mesh(armGeom, sweaterMat);
  lForearm.position.set(0, 0, -0.12);
  lForearm.rotation.x = -1.35;
  lForearmGroup.add(lForearm);

  const lHand = new THREE.Mesh(handGeom, skinMat);
  lHand.scale.set(1.0, 0.6, 1.2);
  lHand.position.set(0, 0.01, -0.25);
  lForearmGroup.add(lHand);

  leftArm.add(lForearmGroup);
  root.add(leftArm);

  // 3D Anchor for Speech Bubble (Directly above Alice's head)
  const speechAnchor = new THREE.Object3D();
  speechAnchor.position.set(0, 1.72, 0.56);
  root.add(speechAnchor);

  let currentGesture = 'idle';

  return {
    root,
    head,
    rightArm,
    leftArm,
    speechAnchor,
    setEmotion: () => {},
    setGesture: (g: string) => {
      currentGesture = g;
    },
    updateAnimation: (time: number) => {
      // Gentle natural breathing
      torsoGroup.position.y = 0.76 + Math.sin(time * 2.2) * 0.008;
      head.position.y = 1.25 + Math.sin(time * 2.2) * 0.008;

      if (currentGesture === 'raise_hand') {
        // Smooth student hand raise to answer or ask question
        rightArm.position.set(0.24, 0.98, 0.58);
        rightArm.rotation.x = 1.1; // Rotates shoulder up & back
        rightArm.rotation.z = -0.25;
        rForearmGroup.rotation.x = 0.4;
        head.rotation.y = -0.25 + Math.sin(time * 2) * 0.04; // Looking eagerly at Bob
        head.rotation.x = -0.05;
      } else if (currentGesture === 'lean_forward') {
        // Engaging peer hint posture
        torsoGroup.rotation.x = -0.14;
        head.rotation.x = 0.08;
        head.rotation.y = 0.35 + Math.sin(time * 1.6) * 0.08; // Turned towards user
        rightArm.rotation.x = 0.1;
        rightArm.rotation.z = 0;
        rForearmGroup.rotation.x = 0;
      } else {
        // Attentive desk posture, taking notes
        torsoGroup.rotation.x = 0;
        rightArm.rotation.x = Math.sin(time * 3.5) * 0.02; // Tiny handwriting wrist motion
        rightArm.rotation.z = 0;
        rForearmGroup.rotation.x = 0;
        // Subtly looking between notebook and chalkboard
        head.rotation.y = -0.18 + Math.sin(time * 0.8) * 0.08;
        head.rotation.x = Math.sin(time * 1.2) * 0.04;
      }
    },
  };
}

/**
 * Creates Charlie the AI Student seated comfortably at his desk.
 *
 * Seating Alignment:
 * - Seated on chair seat at y = 0.46, z = 0.65.
 * - Wearing classic denim jacket with sherpa collar, charcoal beanie, and wireless campus headphones.
 * - Legs bent naturally under the desk, feet planted on floor.
 * - Arms resting on desk with relaxed, curious student posture.
 */
export function createCharlieStudent(): CharacterRig {
  const root = new THREE.Group();
  root.name = 'charlie_student';

  // Materials
  const skinMat = new THREE.MeshStandardMaterial({ color: 0xf3d2bc, roughness: 0.55 });
  const hairMat = new THREE.MeshStandardMaterial({ color: 0x1f1915, roughness: 0.85 }); // Dark brunette / black
  const denimMat = new THREE.MeshStandardMaterial({ color: 0x2b5784, roughness: 0.75 }); // Classic denim blue jacket
  const sherpaMat = new THREE.MeshStandardMaterial({ color: 0xf1f5f9, roughness: 0.95 }); // Soft sherpa collar
  const hoodieMat = new THREE.MeshStandardMaterial({ color: 0x64748b, roughness: 0.8 }); // Heather grey hoodie layer
  const beanieMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.85 }); // Charcoal rib knit beanie
  const jeansMat = new THREE.MeshStandardMaterial({ color: 0x182232, roughness: 0.85 }); // Dark indigo jeans
  const skateShoeMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.5 });
  const whiteSoleMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.4 });
  const headphoneMat = new THREE.MeshStandardMaterial({ color: 0x09090b, roughness: 0.3 });
  const metalMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.8, roughness: 0.2 });

  // 1. Pelvis & Seated Legs
  const pelvis = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.16, 0.26), jeansMat);
  pelvis.position.set(0, 0.51, 0.62);
  pelvis.castShadow = true;
  root.add(pelvis);

  // Thighs extending forward along -Z toward desk
  const thighGeom = new THREE.CapsuleGeometry(0.08, 0.28, 8, 12);
  const leftThigh = new THREE.Mesh(thighGeom, jeansMat);
  leftThigh.rotation.x = Math.PI / 2;
  leftThigh.position.set(-0.12, 0.51, 0.44);
  root.add(leftThigh);

  const rightThigh = new THREE.Mesh(thighGeom, jeansMat);
  rightThigh.rotation.x = Math.PI / 2;
  rightThigh.position.set(0.12, 0.51, 0.44);
  root.add(rightThigh);

  // Shins dropping down from knees
  const shinGeom = new THREE.CapsuleGeometry(0.07, 0.34, 8, 12);
  const leftShin = new THREE.Mesh(shinGeom, jeansMat);
  leftShin.position.set(-0.12, 0.26, 0.28);
  root.add(leftShin);

  const rightShin = new THREE.Mesh(shinGeom, jeansMat);
  rightShin.position.set(0.12, 0.26, 0.28);
  root.add(rightShin);

  // Skate Shoes (Canvas upper + white vulcanized sole)
  const leftShoe = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.07, 0.22), skateShoeMat);
  leftShoe.position.set(-0.12, 0.045, 0.22);
  const leftSole = new THREE.Mesh(new THREE.BoxGeometry(0.125, 0.025, 0.23), whiteSoleMat);
  leftSole.position.set(0, -0.03, 0);
  leftShoe.add(leftSole);
  root.add(leftShoe);

  const rightShoe = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.07, 0.22), skateShoeMat);
  rightShoe.position.set(0.12, 0.045, 0.22);
  const rightSole = new THREE.Mesh(new THREE.BoxGeometry(0.125, 0.025, 0.23), whiteSoleMat);
  rightSole.position.set(0, -0.03, 0);
  rightShoe.add(rightSole);
  root.add(rightShoe);

  // 2. Torso (Denim Jacket over Hoodie)
  const torsoGroup = new THREE.Group();
  torsoGroup.position.set(0, 0.77, 0.60);

  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(0.2, 0.34, 8, 16), denimMat);
  torso.scale.set(1.15, 1.0, 0.85);
  torso.castShadow = true;
  torsoGroup.add(torso);

  // Sherpa Collar
  const sherpaL = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.16, 0.06), sherpaMat);
  sherpaL.position.set(-0.12, 0.18, -0.16);
  sherpaL.rotation.y = 0.25;
  torsoGroup.add(sherpaL);

  const sherpaR = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.16, 0.06), sherpaMat);
  sherpaR.position.set(0.12, 0.18, -0.16);
  sherpaR.rotation.y = -0.25;
  torsoGroup.add(sherpaR);

  // Brass Jacket Snaps
  const snapMat = new THREE.MeshStandardMaterial({ color: 0xd97706, metalness: 0.8, roughness: 0.3 });
  for (let i = 0; i < 3; i++) {
    const snap = new THREE.Mesh(new THREE.SphereGeometry(0.012, 8, 8), snapMat);
    snap.position.set(0, 0.1 - i * 0.1, -0.18);
    torsoGroup.add(snap);
  }

  // Hoodie draped around back of neck
  const hoodBack = new THREE.Mesh(new THREE.CapsuleGeometry(0.14, 0.12, 6, 12), hoodieMat);
  hoodBack.position.set(0, 0.18, 0.14);
  torsoGroup.add(hoodBack);

  root.add(torsoGroup);

  // 3. Head with Modern Beanie & Wireless Headphones
  const head = new THREE.Group();
  head.position.set(0, 1.26, 0.56);

  // Face
  const face = new THREE.Mesh(new THREE.SphereGeometry(0.17, 24, 20), skinMat);
  face.scale.set(0.96, 1.06, 0.96);
  face.castShadow = true;
  head.add(face);

  // Beanie Cap
  const beanieCap = new THREE.Mesh(new THREE.SphereGeometry(0.185, 20, 16), beanieMat);
  beanieCap.scale.set(0.98, 0.85, 1.02);
  beanieCap.position.set(0, 0.12, 0.02);
  head.add(beanieCap);

  // Beanie Ribbed Fold Rim
  const beanieRim = new THREE.Mesh(new THREE.TorusGeometry(0.172, 0.032, 8, 24), beanieMat);
  beanieRim.rotation.x = Math.PI / 2;
  beanieRim.position.set(0, 0.08, 0.01);
  head.add(beanieRim);

  // Wavy fringe hair strands peeking out beneath the beanie
  const fringe1 = new THREE.Mesh(new THREE.CapsuleGeometry(0.035, 0.09, 6, 8), hairMat);
  fringe1.rotation.z = Math.PI * 0.3;
  fringe1.position.set(-0.06, 0.07, -0.145);
  head.add(fringe1);

  const fringe2 = new THREE.Mesh(new THREE.CapsuleGeometry(0.035, 0.09, 6, 8), hairMat);
  fringe2.rotation.z = -Math.PI * 0.3;
  fringe2.position.set(0.05, 0.07, -0.145);
  head.add(fringe2);

  // Wireless Headphones around Neck
  const hpBand = new THREE.Mesh(new THREE.TorusGeometry(0.15, 0.015, 6, 20, Math.PI * 1.1), headphoneMat);
  hpBand.rotation.x = Math.PI * 0.45;
  hpBand.position.set(0, -0.14, 0.02);
  head.add(hpBand);

  // Ear-cushions resting over collarbone
  const earCushionL = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.035, 16), headphoneMat);
  earCushionL.position.set(-0.16, -0.13, -0.06);
  earCushionL.rotation.z = Math.PI * 0.25;
  head.add(earCushionL);

  const earCushionR = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 0.035, 16), headphoneMat);
  earCushionR.position.set(0.16, -0.13, -0.06);
  earCushionR.rotation.z = -Math.PI * 0.25;
  head.add(earCushionR);

  // Ears
  const earGeom = new THREE.SphereGeometry(0.035, 10, 8);
  const earL = new THREE.Mesh(earGeom, skinMat);
  earL.position.set(-0.165, 0, -0.01);
  head.add(earL);

  const earR = new THREE.Mesh(earGeom, skinMat);
  earR.position.set(0.165, 0, -0.01);
  head.add(earR);

  // Expressive Eyes (Facing -Z toward desk & teacher)
  const leftEye = createStylizedEye(0x0f766e, true); // Deep slate teal / ocean eyes
  leftEye.position.set(-0.064, 0.015, -0.148);
  head.add(leftEye);

  const rightEye = createStylizedEye(0x0f766e, false);
  rightEye.position.set(0.064, 0.015, -0.148);
  head.add(rightEye);

  // Expressive Eyebrows
  const browMat = new THREE.MeshBasicMaterial({ color: 0x1f1915 });
  const bL = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.012, 0.015), browMat);
  bL.position.set(-0.064, 0.07, -0.148);
  bL.rotation.z = 0.05;
  head.add(bL);

  const bR = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.012, 0.015), browMat);
  bR.position.set(0.064, 0.07, -0.148);
  bR.rotation.z = -0.05;
  head.add(bR);

  // Nose tip
  const nose = new THREE.Mesh(new THREE.SphereGeometry(0.018, 8, 8), skinMat);
  nose.position.set(0, -0.018, -0.168);
  head.add(nose);

  // Confident friendly mouth
  const mouthMat = new THREE.MeshBasicMaterial({ color: 0xb91c1c });
  const mouth = new THREE.Mesh(new THREE.TorusGeometry(0.026, 0.005, 6, 12, Math.PI * 0.75), mouthMat);
  mouth.rotation.x = -Math.PI * 0.1;
  mouth.position.set(0, -0.065, -0.155);
  head.add(mouth);

  root.add(head);

  // 4. Arms (Relaxed Student Pose resting on desk at y=0.775, z=0.18)
  const armGeom = new THREE.CapsuleGeometry(0.06, 0.24, 8, 12);
  const handGeom = new THREE.SphereGeometry(0.04, 10, 8);

  // Right Arm
  const rightArm = new THREE.Group();
  rightArm.position.set(0.26, 0.98, 0.58);

  const rUpper = new THREE.Mesh(armGeom, denimMat);
  rUpper.position.set(0, -0.12, -0.08);
  rUpper.rotation.x = -0.6;
  rightArm.add(rUpper);

  const rForearmGroup = new THREE.Group();
  rForearmGroup.position.set(0, -0.22, -0.16);

  const rForearm = new THREE.Mesh(armGeom, denimMat);
  rForearm.position.set(0, 0, -0.12);
  rForearm.rotation.x = -1.35;
  rForearmGroup.add(rForearm);

  const rHand = new THREE.Mesh(handGeom, skinMat);
  rHand.scale.set(1.0, 0.6, 1.2);
  rHand.position.set(0, 0.01, -0.25);
  rForearmGroup.add(rHand);

  rightArm.add(rForearmGroup);
  root.add(rightArm);

  // Left Arm
  const leftArm = new THREE.Group();
  leftArm.position.set(-0.26, 0.98, 0.58);

  const lUpper = new THREE.Mesh(armGeom, denimMat);
  lUpper.position.set(0, -0.12, -0.08);
  lUpper.rotation.x = -0.6;
  leftArm.add(lUpper);

  const lForearmGroup = new THREE.Group();
  lForearmGroup.position.set(0, -0.22, -0.16);

  const lForearm = new THREE.Mesh(armGeom, denimMat);
  lForearm.position.set(0, 0, -0.12);
  lForearm.rotation.x = -1.35;
  lForearmGroup.add(lForearm);

  const lHand = new THREE.Mesh(handGeom, skinMat);
  lHand.scale.set(1.0, 0.6, 1.2);
  lHand.position.set(0, 0.01, -0.25);
  lForearmGroup.add(lHand);

  leftArm.add(lForearmGroup);
  root.add(leftArm);

  // 3D Anchor for Speech Bubble
  const speechAnchor = new THREE.Object3D();
  speechAnchor.position.set(0, 1.74, 0.56);
  root.add(speechAnchor);

  let currentGesture = 'idle';

  return {
    root,
    head,
    rightArm,
    leftArm,
    speechAnchor,
    setEmotion: () => {},
    setGesture: (g: string) => {
      currentGesture = g;
    },
    updateAnimation: (time: number) => {
      // Natural student idle breathing
      torsoGroup.position.y = 0.77 + Math.sin(time * 2.3 + 1) * 0.008;
      head.position.y = 1.26 + Math.sin(time * 2.3 + 1) * 0.008;

      if (currentGesture === 'confused_tilt') {
        // Head tilted curiously, scratching ear/neck in puzzled thought
        head.rotation.z = -0.22;
        head.rotation.y = 0.25 + Math.sin(time * 2) * 0.06;
        rightArm.rotation.x = 0.6;
        rightArm.rotation.z = -0.3;
        rForearmGroup.rotation.x = 0.8;
      } else if (currentGesture === 'lean_forward') {
        // Engaged peer discussion posture
        torsoGroup.rotation.x = -0.15;
        head.rotation.x = 0.08;
        head.rotation.y = -0.3 + Math.sin(time * 1.5) * 0.08; // Turned towards user
        rightArm.rotation.x = 0;
        rightArm.rotation.z = 0;
        rForearmGroup.rotation.x = 0;
      } else {
        // Relaxed attentive student posture
        torsoGroup.rotation.x = 0;
        head.rotation.z = 0;
        // Looking naturally between teacher Bob and classmate
        head.rotation.y = 0.2 + Math.sin(time * 0.85 + 2) * 0.07;
        head.rotation.x = Math.sin(time * 1.1) * 0.03;
        rightArm.rotation.x = 0;
        rightArm.rotation.z = 0;
        rForearmGroup.rotation.x = 0;
      }
    },
  };
}

/**
 * Creates a student desk and chair set
 */
export function createDeskAndChair(): THREE.Group {
  const group = new THREE.Group();

  const woodMat = new THREE.MeshStandardMaterial({
    color: 0xc48c5a, // Warm maple wood
    roughness: 0.55,
  });

  const metalMat = new THREE.MeshStandardMaterial({
    color: 0x475569, // Grey steel tubing
    metalness: 0.6,
    roughness: 0.4,
  });

  // Desk Top (Surface at y=0.775)
  const deskTop = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.05, 0.75), woodMat);
  deskTop.position.set(0, 0.75, 0);
  deskTop.castShadow = true;
  deskTop.receiveShadow = true;
  group.add(deskTop);

  // Desk metal frame & 4 legs
  const legGeom = new THREE.CylinderGeometry(0.02, 0.02, 0.75, 8);
  const legPositions = [
    [-0.64, 0.375, -0.32],
    [0.64, 0.375, -0.32],
    [-0.64, 0.375, 0.32],
    [0.64, 0.375, 0.32],
  ];
  legPositions.forEach(([x, y, z]) => {
    const leg = new THREE.Mesh(legGeom, metalMat);
    leg.position.set(x, y, z);
    group.add(leg);
  });

  // Chair Seat & Back (Seat surface at y=0.48, z=0.65)
  const chairSeat = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.04, 0.5), woodMat);
  chairSeat.position.set(0, 0.46, 0.65);
  chairSeat.castShadow = true;
  group.add(chairSeat);

  const chairBack = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.28, 0.03), woodMat);
  chairBack.position.set(0, 0.82, 0.88);
  group.add(chairBack);

  // Chair legs & back supports
  const chairLegGeom = new THREE.CylinderGeometry(0.018, 0.018, 0.46, 8);
  const chairLegs = [
    [-0.24, 0.23, 0.44],
    [0.24, 0.23, 0.44],
    [-0.24, 0.23, 0.86],
    [0.24, 0.23, 0.86],
  ];
  chairLegs.forEach(([x, y, z]) => {
    const leg = new THREE.Mesh(chairLegGeom, metalMat);
    leg.position.set(x, y, z);
    group.add(leg);
  });

  // Back rest posts
  const backPostGeom = new THREE.CylinderGeometry(0.016, 0.016, 0.42, 8);
  const postL = new THREE.Mesh(backPostGeom, metalMat);
  postL.position.set(-0.22, 0.65, 0.87);
  group.add(postL);

  const postR = new THREE.Mesh(backPostGeom, metalMat);
  postR.position.set(0.22, 0.65, 0.87);
  group.add(postR);

  return group;
}

/**
 * Creates decorative props like notebooks, pen, pencil, and laptop
 */
export function createDeskProps(hasLaptop = false): THREE.Group {
  const group = new THREE.Group();

  // Notebook
  const bookMat = new THREE.MeshStandardMaterial({ color: 0x2563eb, roughness: 0.5 });
  const paperMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc, roughness: 0.8 });
  const cover = new THREE.Mesh(new THREE.BoxGeometry(0.26, 0.015, 0.34), bookMat);
  cover.position.set(0.22, 0.78, 0.05);
  cover.rotation.y = 0.12;
  group.add(cover);

  const pages = new THREE.Mesh(new THREE.BoxGeometry(0.24, 0.012, 0.32), paperMat);
  pages.position.set(0.22, 0.79, 0.05);
  pages.rotation.y = 0.12;
  group.add(pages);

  // Pen
  const penMat = new THREE.MeshStandardMaterial({ color: 0xdc2626 });
  const pen = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.005, 0.18, 8), penMat);
  pen.rotation.x = Math.PI / 2;
  pen.rotation.z = -0.3;
  pen.position.set(0.06, 0.78, 0.1);
  group.add(pen);

  if (hasLaptop) {
    const laptopMat = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.7, roughness: 0.3 });
    const screenMat = new THREE.MeshBasicMaterial({ color: 0x0284c7 });
    const base = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.01, 0.22), laptopMat);
    base.position.set(-0.22, 0.78, 0);
    group.add(base);

    const lid = new THREE.Mesh(new THREE.BoxGeometry(0.32, 0.22, 0.01), laptopMat);
    lid.position.set(-0.22, 0.88, -0.1);
    lid.rotation.x = -0.2;
    group.add(lid);

    const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.29, 0.18), screenMat);
    screen.position.set(-0.22, 0.88, -0.094);
    screen.rotation.x = -0.2;
    group.add(screen);
  }

  return group;
}
