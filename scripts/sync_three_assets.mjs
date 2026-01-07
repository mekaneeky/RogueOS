#!/usr/bin/env node

import { mkdir, readFile, copyFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const CURRENT_FILE = fileURLToPath(import.meta.url);
const PROJECT_ROOT = path.resolve(path.dirname(CURRENT_FILE), '..');
const NODE_MODULES_DIR = path.join(PROJECT_ROOT, 'node_modules');
const THREE_ROOT = path.join(NODE_MODULES_DIR, 'three');
const VENDOR_DIR = path.join(PROJECT_ROOT, 'rogueos_web', 'static', 'vendor');

const ASSETS = [
  {
    dest: ['build', 'three.module.js'],
    src: ['build', 'three.module.js']
  },
  {
    dest: ['examples', 'jsm', 'controls', 'OrbitControls.js'],
    src: ['examples', 'jsm', 'controls', 'OrbitControls.js']
  },
  {
    dest: ['examples', 'jsm', 'postprocessing', 'EffectComposer.js'],
    src: ['examples', 'jsm', 'postprocessing', 'EffectComposer.js']
  },
  {
    dest: ['examples', 'jsm', 'postprocessing', 'RenderPass.js'],
    src: ['examples', 'jsm', 'postprocessing', 'RenderPass.js']
  },
  {
    dest: ['examples', 'jsm', 'postprocessing', 'UnrealBloomPass.js'],
    src: ['examples', 'jsm', 'postprocessing', 'UnrealBloomPass.js']
  },
  {
    dest: ['examples', 'jsm', 'postprocessing', 'FilmPass.js'],
    src: ['examples', 'jsm', 'postprocessing', 'FilmPass.js']
  },
  {
    dest: ['examples', 'jsm', 'postprocessing', 'ShaderPass.js'],
    src: ['examples', 'jsm', 'postprocessing', 'ShaderPass.js']
  },
  {
    dest: ['examples', 'jsm', 'postprocessing', 'Pass.js'],
    src: ['examples', 'jsm', 'postprocessing', 'Pass.js']
  },
  {
    dest: ['examples', 'jsm', 'postprocessing', 'MaskPass.js'],
    src: ['examples', 'jsm', 'postprocessing', 'MaskPass.js']
  },
  {
    dest: ['examples', 'jsm', 'shaders', 'FXAAShader.js'],
    src: ['examples', 'jsm', 'shaders', 'FXAAShader.js']
  },
  {
    dest: ['examples', 'jsm', 'shaders', 'LuminosityShader.js'],
    src: ['examples', 'jsm', 'shaders', 'LuminosityShader.js']
  },
  {
    dest: ['examples', 'jsm', 'shaders', 'ColorCorrectionShader.js'],
    src: ['examples', 'jsm', 'shaders', 'ColorCorrectionShader.js']
  },
  {
    dest: ['examples', 'jsm', 'shaders', 'CopyShader.js'],
    src: ['examples', 'jsm', 'shaders', 'CopyShader.js']
  },
  {
    dest: ['examples', 'jsm', 'shaders', 'FilmShader.js'],
    src: ['examples', 'jsm', 'shaders', 'FilmShader.js']
  },
  {
    dest: ['examples', 'jsm', 'shaders', 'LuminosityHighPassShader.js'],
    src: ['examples', 'jsm', 'shaders', 'LuminosityHighPassShader.js']
  }
];

async function fileSha256(filePath) {
  try {
    const data = await readFile(filePath);
    return createHash('sha256').update(data).digest('hex');
  } catch (err) {
    if (err.code === 'ENOENT') return null;
    throw err;
  }
}

async function syncAssets() {
  try {
    await mkdir(VENDOR_DIR, { recursive: true });
  } catch (err) {
    console.error('Failed to create vendor directory', VENDOR_DIR, err);
    process.exitCode = 1;
    return;
  }

  for (const asset of ASSETS) {
    const { dest, src } = asset;
    const displayName = dest.join('/');
    const source = path.join(THREE_ROOT, ...src);
    const target = path.join(VENDOR_DIR, ...dest);

    const beforeHash = await fileSha256(source);
    if (!beforeHash) {
      console.error(`Missing asset "${displayName}". Did you run "npm install"?`);
      process.exitCode = 1;
      return;
    }

    await mkdir(path.dirname(target), { recursive: true });

    const existingHash = await fileSha256(target);
    if (existingHash === beforeHash) {
      console.log(`= ${displayName} (unchanged)`);
      continue;
    }

    await copyFile(source, target);
    const afterHash = await fileSha256(target);
    const summary = afterHash?.slice(0, 12) ?? 'unknown';
    console.log(`✔ ${displayName} (${summary})`);
  }
}

syncAssets().catch((err) => {
  console.error('Failed to sync Three.js assets:', err);
  process.exitCode = 1;
});
