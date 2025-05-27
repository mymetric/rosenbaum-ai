with last_phone as (
    select
        chat_phone phone,
        account_email email,
        max(created_at) last_message,
        count(*) message_count,
        count(case when ocr_scan is not null then 1 end) as ocr_count,
        count(case when audio_transcription is not null then 1 end) as audio_count
    from `zapy-306602.gtms.messages`
    where chat_phone is not null or account_email is not null
    group by chat_phone, account_email
)

SELECT
    a.id,
    a.created_at,
    a.board,
    a.title,
    a.phone,
    COALESCE(a.email, '') as email,
    a.monday_link,
    b.last_message,
    b.message_count,
    COALESCE(b.ocr_count, 0) as ocr_count,
    COALESCE(b.audio_count, 0) as audio_count
FROM `zapy-306602.dbt.monday_sessions` a
left join last_phone b on (a.phone = b.phone or a.email = b.email)
ORDER BY created_at DESC 