export interface LocatePcResult {
  ok: boolean
  lat?: number
  lng?: number
  accuracy?: number
  via?: 'windows' | 'corelocation' | 'ipwho.is' | 'ipapi.co' | 'freeipapi.com'
  code?: 'DENIED' | 'TIMEOUT' | 'UNKNOWN' | 'ERROR' | 'SPAWN_FAILED' | 'NODATA' | 'ALL_FAILED'
  message?: string
}

export type RenderMode = 'hardware' | 'software'

export interface RenderModeInfo {
  mode: RenderMode
  saved: RenderMode | null
  isWin10: boolean
}

declare global {
  interface Window {
    electronAPI?: {
      platform?: 'darwin' | 'win32' | 'linux' | string
      locatePc(): Promise<LocatePcResult>
      getRenderMode(): Promise<RenderModeInfo>
      setRenderMode(mode: RenderMode): Promise<{ ok: boolean }>
      relaunchApp(): Promise<void>
    }
  }
}

export {}
