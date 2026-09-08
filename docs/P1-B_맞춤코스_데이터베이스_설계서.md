# P1-B 맞춤 코스 데이터베이스 설계서

## 1. 목적

P1-B 맞춤 코스는 시설별 관람 시간과 이동 시간을 합산해 제한 시간 안의 코스만 추천한다.
현재는 JSON Mock으로 시작하고, 이후 PostgreSQL과 pgvector 기반 RAG로 전환할 수 있도록 데이터 경계를 분리한다.

## 2. 데이터 소유와 사용처

| 데이터 | 현재 위치 | 담당 | 사용처 |
| --- | --- | --- | --- |
| 시설 기본 정보·별칭 | `data/operations/habitats.json` | 최두나 | 시설명 정규화 |
| 코스 메타데이터 | `data/operations/course_profiles.json` | 최두나 | 관람 시간·아이·날씨 판단 |
| 이동 경로 | `data/operations/routes.json` | 최두나 | 구간별 이동 시간 |
| 휴장 상태 | `data/operations/closures.json` | 최두나 | 추천 후보 제외 |
| 동물 정보카드 | `data/animal_cards/*.json`, `data/*.md` | 최두나 | RAG 검색 근거 |

손영민은 위 데이터를 읽는 계약과 Planner 검증을 구현한다. 이원민은 날씨 MCP Tool과 코스 화면을 구현한다.

## 3. JSON Mock 계약

새 파일 `data/operations/course_profiles.json`을 사용한다.

```json
{
  "profiles": [
    {
      "habitat": "정문",
      "visit_minutes": 0,
      "child_friendly": false,
      "indoor": false,
      "is_entry": true
    },
    {
      "habitat": "해양관",
      "visit_minutes": 25,
      "child_friendly": true,
      "indoor": true,
      "is_entry": false
    },
    {
      "habitat": "호랑이관",
      "visit_minutes": 20,
      "child_friendly": false,
      "indoor": false,
      "is_entry": false
    },
    {
      "habitat": "코끼리관",
      "visit_minutes": 20,
      "child_friendly": true,
      "indoor": false,
      "is_entry": false
    },
    {
      "habitat": "기린관",
      "visit_minutes": 20,
      "child_friendly": true,
      "indoor": false,
      "is_entry": false
    }
  ]
}
```

### 필드 규칙

| 필드 | 형식 | 규칙 |
| --- | --- | --- |
| `habitat` | 문자열 | `habitats.json`의 정규 시설명과 정확히 일치 |
| `visit_minutes` | 정수 | 0 이상. 정문은 0, 추천 대상 시설은 1 이상 |
| `child_friendly` | 불리언 | 아이 동반 코스의 우선순위 판단에 사용 |
| `indoor` | 불리언 | 비·악천후 시 실내 시설 우선순위 판단에 사용 |
| `is_entry` | 불리언 | `true`인 시설은 출발점이며 추천 방문 대상에서 제외 |

위 값은 실제 운영 정보가 아닌 P1-B 시연용 Mock 기준이다.

## 4. PostgreSQL 전환 설계

### 4.1 운영·코스 관계형 테이블

```sql
CREATE TABLE habitats (
    habitat_id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    visit_minutes INTEGER NOT NULL CHECK (visit_minutes >= 0),
    child_friendly BOOLEAN NOT NULL DEFAULT FALSE,
    indoor BOOLEAN NOT NULL DEFAULT FALSE,
    is_entry BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE habitat_aliases (
    alias VARCHAR(100) PRIMARY KEY,
    habitat_id BIGINT NOT NULL REFERENCES habitats(habitat_id)
);

CREATE TABLE habitat_routes (
    route_id BIGSERIAL PRIMARY KEY,
    current_habitat_id BIGINT NOT NULL REFERENCES habitats(habitat_id),
    destination_habitat_id BIGINT NOT NULL REFERENCES habitats(habitat_id),
    path_json JSONB NOT NULL,
    estimated_minutes INTEGER NOT NULL CHECK (estimated_minutes >= 0),
    UNIQUE (current_habitat_id, destination_habitat_id)
);

CREATE TABLE habitat_closures (
    closure_id BIGSERIAL PRIMARY KEY,
    habitat_id BIGINT NOT NULL REFERENCES habitats(habitat_id),
    closed BOOLEAN NOT NULL,
    reason TEXT,
    as_of TIMESTAMPTZ NOT NULL
);
```

`path_json`은 기존 `routes.json`의 `path` 배열을 그대로 옮긴다. 폐장 상태는 시점별 이력이 필요하므로 시설 테이블에 직접 넣지 않는다.

### 4.2 RAG·pgvector 테이블

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE rag_documents (
    document_id VARCHAR(200) PRIMARY KEY,
    collection VARCHAR(100) NOT NULL,
    title TEXT NOT NULL,
    source_path TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE rag_chunks (
    chunk_id BIGSERIAL PRIMARY KEY,
    document_id VARCHAR(200) NOT NULL REFERENCES rag_documents(document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(<EMBEDDING_DIMENSION>) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (document_id, chunk_index)
);
```

`<EMBEDDING_DIMENSION>`은 선택한 임베딩 모델의 차원으로 확정한다. 모델을 바꾸면 새 컬럼·인덱스를 만들고 전체 Chunk 임베딩을 다시 생성한다.

예시 인덱스는 다음과 같다.

```sql
CREATE INDEX rag_chunks_embedding_hnsw_idx
ON rag_chunks USING hnsw (embedding vector_cosine_ops);

CREATE INDEX rag_documents_collection_idx
ON rag_documents (collection);
```

## 5. Mock 데이터 생성·이관 규칙

1. 시설명은 `habitats.json`을 기준값으로 사용하고, 다른 JSON·RAG 문서에서 새 시설명을 임의로 만들지 않는다.
2. `course_profiles.json`의 모든 `habitat`은 `habitats.json`에 존재해야 한다.
3. 각 추천 대상 시설은 출발점에서 접근 가능한 경로를 최소 하나 가져야 한다.
4. `visit_minutes`는 정수 분 단위로 저장하며, 이동 시간과 같은 단위로 계산한다.
5. 동물 카드 JSON·MD를 RAG 문서로 넣을 때 `document_id`, 제목, 원본 경로, 동물명·시설명 같은 메타데이터를 함께 저장한다.
6. RAG 검색 결과는 문서·Chunk·점수 근거를 응답에 반환한다. Planner는 RAG 문장 자체가 아니라 운영 테이블의 시간·휴장·경로만으로 시간 제한을 검증한다.

## 6. 데이터 검증 기준

- 해양관→기린관→코끼리관은 정문 출발 기준 총 115분이다.
- 휴장된 코끼리관은 코스 후보에서 제외된다.
- 같은 시설은 코스에 한 번만 포함되며 관람 시간도 한 번만 합산한다.
- `is_entry=true` 시설은 출발점으로만 사용한다.
- 시설·경로·휴장·코스 프로필 데이터의 참조 무결성을 Mock 테스트와 DB 제약으로 검증한다.
