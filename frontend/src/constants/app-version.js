/** 与根目录 VERSION / package.json 对齐 — 构建时注入 */
import pkg from '../../package.json'

export const APP_VERSION = pkg.version
