import type { AssistantPhase } from './assistantState'

export type PetState = 'idle' | 'thinking' | 'listening' | 'speaking' | 'error'

// Speaking is supplied by actual PCM playback through assistantPhase, never transcript arrival.
export function petState(phase: AssistantPhase): PetState {
  switch (phase) {
    case 'connecting':
      return 'thinking'
    case 'listening':
      return 'listening'
    case 'speaking':
      return 'speaking'
    case 'unavailable':
      return 'error'
    default:
      return 'idle'
  }
}
