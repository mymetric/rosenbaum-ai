SELECT
  created_at,
  message_text,
  file_url attachment_url,
  audio_transcription,
  ocr_scan,
  message_direction
FROM `zapy-306602.gtms.messages`
WHERE
    chat_phone = @phone
    -- AND TRIM(message_text) != ''
    -- AND message_text IS NOT NULL
    
ORDER BY created_at DESC 