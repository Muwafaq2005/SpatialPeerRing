import React from 'react';

export const Lighting: React.FC = () => {
  return (
    <>
      <ambientLight intensity={0.7} />
      <directionalLight
        position={[5, 8, 5]}
        intensity={1.2}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
      />
      <pointLight position={[-5, 4, -2]} intensity={0.5} color="#4f46e5" />
      <pointLight position={[5, 4, -2]} intensity={0.5} color="#06b6d4" />
    </>
  );
};
