import React from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';
import { Lighting } from './Lighting';
import { Avatar } from './Avatar';

interface StudyPodProps {
  activeSpeaker: string;
}

export const StudyPod: React.FC<StudyPodProps> = ({ activeSpeaker }) => {
  return (
    <div style={{ width: '100%', height: '100%', position: 'relative', borderRadius: '16px', overflow: 'hidden' }}>
      <Canvas shadows>
        <PerspectiveCamera makeDefault position={[0, 1.8, 5.2]} fov={50} />
        <OrbitControls
          enablePan={false}
          maxPolarAngle={Math.PI / 2 - 0.05}
          minDistance={3.5}
          maxDistance={7.5}
        />
        <Lighting />

        {/* Floor grid plane */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.9, 0]} receiveShadow>
          <planeGeometry args={[16, 16]} />
          <meshStandardMaterial color="#0f172a" roughness={0.8} />
        </mesh>

        {/* 3D Blackboard Mesh Frame in background */}
        <group position={[0, 1.2, -2.5]}>
          {/* Outer Frame */}
          <mesh>
            <boxGeometry args={[4.4, 2.4, 0.1]} />
            <meshStandardMaterial color="#334155" roughness={0.4} />
          </mesh>
          {/* Blackboard Surface */}
          <mesh position={[0, 0, 0.06]}>
            <planeGeometry args={[4.2, 2.2]} />
            <meshStandardMaterial color="#022c22" roughness={0.6} />
          </mesh>
        </group>

        {/* Bob Socratic Tutor (Center High) */}
        <Avatar
          id="bob-tutor"
          name="Bob"
          role="Socratic Tutor"
          color="#3b82f6"
          accentColor="#60a5fa"
          position={[0, 0.1, -0.8]}
          isSpeaking={activeSpeaker === 'bob-tutor'}
        />

        {/* Alice Arithmetic Peer (Left) */}
        <Avatar
          id="alice-arithmetic"
          name="Alice"
          role="Arithmetic Peer"
          color="#ec4899"
          accentColor="#f472b6"
          position={[-1.9, -0.1, 0.8]}
          isSpeaking={activeSpeaker === 'alice-arithmetic'}
        />

        {/* Charlie Conceptual Peer (Right) */}
        <Avatar
          id="charlie-conceptual"
          name="Charlie"
          role="Conceptual Peer"
          color="#8b5cf6"
          accentColor="#a78bfa"
          position={[1.9, -0.1, 0.8]}
          isSpeaking={activeSpeaker === 'charlie-conceptual'}
        />

        {/* User Student (Bottom Front) */}
        <Avatar
          id="user"
          name="You"
          role="Student"
          color="#10b981"
          accentColor="#34d399"
          position={[0, -0.4, 2.4]}
          isSpeaking={activeSpeaker === 'user'}
        />
      </Canvas>
    </div>
  );
};
