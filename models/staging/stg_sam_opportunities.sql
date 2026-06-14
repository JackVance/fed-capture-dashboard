{{ config(materialized='view') }}

WITH source AS (

    SELECT * FROM {{ source('raw', 'sam_opportunities') }}

),

transformed AS (

    SELECT
        -- Identifiers
        notice_id,
        raw:solicitationNumber::VARCHAR                            AS solicitation_number,

        -- Dates
        posted_date,
        response_deadline,
        TRY_TO_DATE(raw:archiveDate::VARCHAR)                      AS archive_date,
        raw:archiveType::VARCHAR                                   AS archive_type,

        -- Classification
        naics_code,
        raw:classificationCode::VARCHAR                            AS psc_code,
        notice_type,
        raw:baseType::VARCHAR                                      AS base_notice_type,

        -- Status & qualification
        is_active,
        type_of_set_aside,

        -- Display fields
        raw:title::VARCHAR                                         AS title,
        raw:fullParentPathName::VARCHAR                            AS agency_path,

        -- Location
        state,
        raw:placeOfPerformance:country:code::VARCHAR               AS country_code,
        raw:placeOfPerformance:zip::VARCHAR                        AS zip_code,
        (raw:placeOfPerformance:country:code::VARCHAR = 'USA')     AS is_us_location,

        -- Links and attachments
        raw:uiLink::VARCHAR                                        AS ui_link,
        raw:description::VARCHAR                                   AS description_url,
        COALESCE(ARRAY_SIZE(raw:resourceLinks) > 0, FALSE)         AS has_attachments,

        -- Metadata
        ingested_at

    FROM source
    WHERE notice_id IS NOT NULL  -- defensive: drop any malformed rows

)

SELECT * FROM transformed