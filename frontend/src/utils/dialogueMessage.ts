export const SCENE_OPENING_EVENT_MARKER = '[SCENE_OPENING_EVENT]'

export const isInternalPromptText = (value: unknown) =>
  String(value ?? '').includes(SCENE_OPENING_EVENT_MARKER)

export const isInternalPromptMessage = (message: any) =>
  isInternalPromptText(message?.content ?? message?.text)
