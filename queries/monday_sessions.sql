with last_phone as (
    select
        chat_phone phone,
        max(created_at) last_message,
        count(*) message_count
    from `zapy-306602.gtms.messages`
    group by all
)

SELECT
    a.id,
    a.created_at,
    a.board,
    a.title,
    a.phone,
    a.monday_link,
    b.last_message,
    b.message_count
FROM `zapy-306602.dbt.monday_sessions` a
left join last_phone b on a.phone = b.phone
ORDER BY created_at DESC 