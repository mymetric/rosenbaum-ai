SELECT
  created_at,
  message_text,
  file_url as attachment_url,
  audio_transcription,
  ocr_scan,
  message_direction,
  attachment_filename
FROM `zapy-306602.gtms.messages`
WHERE
    (chat_phone = @phone OR account_email = @email)
    AND (chat_phone IS NOT NULL OR account_email IS NOT NULL)
    -- AND TRIM(message_text) != ''
    -- AND message_text IS NOT NULL
    
ORDER BY created_at DESC 