import * as ThreeModule from 'three';

import { OrbitControls } from './examples/jsm/controls/OrbitControls.js';
import { EffectComposer } from './examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from './examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from './examples/jsm/postprocessing/UnrealBloomPass.js';
import { FilmPass } from './examples/jsm/postprocessing/FilmPass.js';
import { ShaderPass } from './examples/jsm/postprocessing/ShaderPass.js';
import { Pass } from './examples/jsm/postprocessing/Pass.js';
import { MaskPass, ClearMaskPass } from './examples/jsm/postprocessing/MaskPass.js';

import { FXAAShader } from './examples/jsm/shaders/FXAAShader.js';
import { LuminosityShader } from './examples/jsm/shaders/LuminosityShader.js';
import { ColorCorrectionShader } from './examples/jsm/shaders/ColorCorrectionShader.js';
import { CopyShader } from './examples/jsm/shaders/CopyShader.js';
import { FilmShader } from './examples/jsm/shaders/FilmShader.js';
import { LuminosityHighPassShader } from './examples/jsm/shaders/LuminosityHighPassShader.js';

let globalThree = null;

function copyNamespace(source) {
  const target = {};
  for (const key of Reflect.ownKeys(source)) {
    if (key === 'default' || key === '__esModule') continue;
    const descriptor = Object.getOwnPropertyDescriptor(source, key);
    if (descriptor) {
      Object.defineProperty(target, key, descriptor);
    }
  }
  return target;
}

function buildThree() {
  const base = copyNamespace(ThreeModule);
  Object.assign(base, {
    OrbitControls,
    EffectComposer,
    RenderPass,
    UnrealBloomPass,
    FilmPass,
    ShaderPass,
    Pass,
    MaskPass,
    ClearMaskPass,
    FXAAShader,
    LuminosityShader,
    ColorCorrectionShader,
    CopyShader,
    FilmShader,
    LuminosityHighPassShader
  });
  return base;
}

export function setupThreeGlobals() {
  if (!globalThree) {
    globalThree = buildThree();
    if (typeof window !== 'undefined') {
      window.THREE = globalThree;
    }
  }
  return globalThree;
}

export default setupThreeGlobals;
