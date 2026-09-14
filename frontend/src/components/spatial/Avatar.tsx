import React, { useRef } from 'react';
import { useFrame } from '@react-three/fiber';
import { Html } from '@react-three/drei';
import * as THREE from 'three';

interface AvatarProps {
  id: string;
  name: string;
  role: string;
  color: string;
  accentColor: string;
  position: [number, number, number];
  isSpeaking: boolean;
}

export const Avatar: React.FC<AvatarProps> = ({
  name,
  role,
  color,
  accentColor,
  position,
  isSpeaking,
}) => {
  const meshRef = useRef<THREE.Group>(null);
  const headRef = useRef<THREE.Mesh>(null);
  const ringRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();

    if (meshRef.current) {
      // Gentle breathing idle floating
      meshRef.current.position.y = position[1] + Math.sin(t * 2) * 0.05;
    }

    if (headRef.current && isSpeaking) {
      // Bobbing head motion when speaking
      headRef.current.rotation.y = Math.sin(t * 8) * 0.15;
    } else if (headRef.current) {
      headRef.current.rotation.y = THREE.MathUtils.lerp(headRef.current.rotation.y, 0, 0.1);
    }

    if (ringRef.current) {
      ringRef.current.rotation.z = t * 1.5;
    }
  });

  return (
    <group ref={meshRef} position={position}>
      {/* Active speaker aura glow ring */}
      {isSpeaking && (
        <mesh ref={ringRef} position={[0, -0.6, 0]} rotation={[-Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.7, 0.85, 32]} />
          <meshBasicMaterial color={accentColor} side={THREE.DoubleSide} transparent opacity={0.8} />
        </mesh>
      )}

      {/* Body capsule */}
      <mesh position={[0, 0, 0]} castShadow>
        <cylinderGeometry args={[0.35, 0.45, 1.0, 16]} />
        <meshStandardMaterial color={color} roughness={0.3} metalness={0.2} />
      </mesh>

      {/* Head Sphere */}
      <mesh ref={headRef} position={[0, 0.8, 0]} castShadow>
        <sphereGeometry args={[0.35, 32, 32]} />
        <meshStandardMaterial color={isSpeaking ? accentColor : color} roughness={0.2} />
      </mesh>

      {/* Floating Name Badge */}
      <Html position={[0, 1.35, 0]} center distanceFactor={8}>
        <div
          style={{
            background: isSpeaking ? 'rgba(79, 70, 229, 0.9)' : 'rgba(15, 23, 42, 0.85)',
            border: `1px solid ${isSpeaking ? accentColor : 'rgba(255, 255, 255, 0.2)'}`,
            padding: '4px 10px',
            borderRadius: '12px',
            color: '#ffffff',
            fontSize: '12px',
            fontWeight: 600,
            whiteSpace: 'nowrap',
            boxShadow: isSpeaking ? `0 0 12px ${accentColor}` : 'none',
            transition: 'all 0.3s ease',
            textAlign: 'center',
          }}
        >
          <div>{name}</div>
          <div style={{ fontSize: '10px', opacity: 0.8, fontWeight: 400 }}>{role}</div>
        </div>
      </Html>
    </group>
  );
};
