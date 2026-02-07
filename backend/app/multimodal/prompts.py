"""
Prompt templates for multimodal content processing.
Inspired by RAG-Anything's prompt system.
"""

PROMPTS = {}

# ============================================================
# System prompts
# ============================================================
PROMPTS["IMAGE_ANALYSIS_SYSTEM"] = (
    "You are an expert image analyst. Provide detailed, accurate descriptions."
)
PROMPTS["TABLE_ANALYSIS_SYSTEM"] = (
    "You are an expert data analyst. Provide detailed table analysis with specific insights."
)
PROMPTS["EQUATION_ANALYSIS_SYSTEM"] = (
    "You are an expert mathematician. Provide detailed mathematical analysis."
)
PROMPTS["GENERIC_ANALYSIS_SYSTEM"] = (
    "You are an expert content analyst specializing in {content_type} content."
)

# ============================================================
# Image prompts
# ============================================================
PROMPTS["vision_prompt"] = """Analyze this image in detail. Provide a JSON response:

{{
    "detailed_description": "A comprehensive visual description covering:
    - Overall composition and layout
    - All objects, people, text, visual elements
    - Relationships between elements
    - Colors, lighting, visual style
    - Actions or activities shown
    - Technical details (charts, diagrams, etc.)
    Use specific names instead of pronouns.",
    "entity_info": {{
        "entity_name": "{entity_name}",
        "entity_type": "image",
        "summary": "concise summary of the image content (max 100 words)"
    }}
}}

Image Path: {image_path}
Captions: {captions}
Footnotes: {footnotes}"""

PROMPTS["vision_prompt_with_context"] = """Analyze this image considering the surrounding context. Provide a JSON response:

{{
    "detailed_description": "A comprehensive visual description covering:
    - Overall composition and layout
    - All objects, people, text, visual elements
    - Relationships to the surrounding content context
    - Colors, lighting, visual style
    - Technical details (charts, diagrams, etc.)
    Use specific names instead of pronouns.",
    "entity_info": {{
        "entity_name": "{entity_name}",
        "entity_type": "image",
        "summary": "concise summary of image content and its context (max 100 words)"
    }}
}}

Context from surrounding content:
{context}

Image Path: {image_path}
Captions: {captions}
Footnotes: {footnotes}"""

# ============================================================
# Table prompts
# ============================================================
PROMPTS["table_prompt"] = """Analyze this table content. Provide a JSON response:

{{
    "detailed_description": "A comprehensive table analysis covering:
    - Table structure and organization
    - Column headers and meanings
    - Key data points and patterns
    - Statistical insights and trends
    - Relationships between data elements
    Use specific names and values.",
    "entity_info": {{
        "entity_name": "{entity_name}",
        "entity_type": "table",
        "summary": "concise summary of the table purpose and key findings (max 100 words)"
    }}
}}

Caption: {table_caption}
Body: {table_body}
Footnotes: {table_footnote}"""

PROMPTS["table_prompt_with_context"] = """Analyze this table considering surrounding context. Provide a JSON response:

{{
    "detailed_description": "A comprehensive table analysis covering:
    - Table structure and organization
    - Column headers and meanings
    - Key data points and patterns
    - Relationships to surrounding content
    Use specific names and values.",
    "entity_info": {{
        "entity_name": "{entity_name}",
        "entity_type": "table",
        "summary": "concise summary of table and its context (max 100 words)"
    }}
}}

Context from surrounding content:
{context}

Caption: {table_caption}
Body: {table_body}
Footnotes: {table_footnote}"""

# ============================================================
# Equation prompts
# ============================================================
PROMPTS["equation_prompt"] = """Analyze this mathematical equation. Provide a JSON response:

{{
    "detailed_description": "A comprehensive analysis covering:
    - Mathematical meaning and interpretation
    - Variables and definitions
    - Operations and functions used
    - Application domain
    - Theoretical significance
    Use specific mathematical terminology.",
    "entity_info": {{
        "entity_name": "{entity_name}",
        "entity_type": "equation",
        "summary": "concise summary of the equation purpose (max 100 words)"
    }}
}}

Equation: {equation_text}
Format: {equation_format}"""

PROMPTS["equation_prompt_with_context"] = """Analyze this equation considering surrounding context. Provide a JSON response:

{{
    "detailed_description": "A comprehensive analysis covering:
    - Mathematical meaning and interpretation
    - Variables in context of surrounding content
    - Operations and functions used
    - How equation relates to broader discussion
    Use specific mathematical terminology.",
    "entity_info": {{
        "entity_name": "{entity_name}",
        "entity_type": "equation",
        "summary": "concise summary of equation and its context (max 100 words)"
    }}
}}

Context from surrounding content:
{context}

Equation: {equation_text}
Format: {equation_format}"""

# ============================================================
# Generic prompts
# ============================================================
PROMPTS["generic_prompt"] = """Analyze this {content_type} content. Provide a JSON response:

{{
    "detailed_description": "A comprehensive analysis covering:
    - Content structure and organization
    - Key information and elements
    - Relationships between components
    - Context and significance
    Use specific terminology.",
    "entity_info": {{
        "entity_name": "{entity_name}",
        "entity_type": "{content_type}",
        "summary": "concise summary of key points (max 100 words)"
    }}
}}

Content: {content}"""

# ============================================================
# Chunk templates (for storing analyzed multimodal content)
# ============================================================
PROMPTS["image_chunk"] = """[IMAGE CONTENT]
Image: {image_path}
Captions: {captions}
Footnotes: {footnotes}

Visual Analysis: {enhanced_caption}"""

PROMPTS["table_chunk"] = """[TABLE CONTENT]
Caption: {table_caption}
Structure: {table_body}
Footnotes: {table_footnote}

Analysis: {enhanced_caption}"""

PROMPTS["equation_chunk"] = """[EQUATION CONTENT]
Equation: {equation_text}
Format: {equation_format}

Mathematical Analysis: {enhanced_caption}"""

PROMPTS["generic_chunk"] = """[{content_type} CONTENT]
Content: {content}

Analysis: {enhanced_caption}"""

# ============================================================
# Query prompts
# ============================================================
PROMPTS["QUERY_IMAGE_DESCRIPTION"] = (
    "Briefly describe the main content, key elements, and important information in this image."
)
PROMPTS["QUERY_TABLE_ANALYSIS"] = """Analyze the main content and key information of this table:

Table data: {table_data}
Caption: {table_caption}

Briefly summarize the main content, data characteristics, and important findings."""

PROMPTS["QUERY_EQUATION_ANALYSIS"] = """Explain the meaning of this mathematical formula:

LaTeX formula: {latex}
Caption: {equation_caption}

Briefly explain the mathematical meaning and importance."""

PROMPTS["QUERY_ENHANCEMENT_SUFFIX"] = (
    "\n\nProvide a comprehensive answer based on the user query and the provided multimodal content."
)

# ============================================================
# RAG system prompts
# ============================================================
PROMPTS["RAG_SYSTEM"] = """You are a helpful AI assistant for a company knowledge base.
Answer questions based on the provided context from documents.
If the context doesn't contain enough information, say so.
Always cite your sources when possible.
Support multimodal content including images, tables, and equations."""

PROMPTS["RAG_QUERY_WITH_CONTEXT"] = """Based on the following context from company documents, answer the question.

Context:
{context}

{graph_context}

{multimodal_context}

Question: {question}

Instructions:
- Answer based on the provided context
- Cite specific documents when possible
- If context is insufficient, say so clearly
- Include relevant information from images, tables, or equations if present
- Be concise but thorough"""

PROMPTS["ENTITY_EXTRACTION"] = """Analyze the following text and extract entities and relationships.

Text:
{text}

Return ONLY valid JSON:
{{
  "entities": [
    {{"name": "Entity Name", "type": "PERSON|ORGANIZATION|PROJECT|TECHNOLOGY|PRODUCT|LOCATION|CONCEPT"}}
  ],
  "relations": [
    {{"source": "Entity1", "target": "Entity2", "relation": "WORKS_FOR|CEO_OF|CREATED_BY|PART_OF|USES|INTEGRATES_WITH|RELATED_TO|MANAGES|DEPENDS_ON|LOCATED_IN"}}
  ]
}}

Rules:
- Entity names should be normalized (capitalize properly)
- Only extract clear, explicit relationships
- Keep entity names concise
- Return empty arrays if no entities/relations found"""

PROMPTS["MULTIMODAL_ENTITY_EXTRACTION"] = """Analyze this multimodal content and extract entities and relationships.

Content Type: {content_type}
Description: {description}
Source Document: {source_doc}

Return ONLY valid JSON:
{{
  "entities": [
    {{"name": "Entity Name", "type": "PERSON|ORGANIZATION|PROJECT|TECHNOLOGY|PRODUCT|LOCATION|CONCEPT|IMAGE|TABLE|EQUATION"}}
  ],
  "relations": [
    {{"source": "Entity1", "target": "Entity2", "relation": "CONTAINS|DESCRIBES|REFERENCES|PART_OF|RELATED_TO|VISUALIZES|QUANTIFIES"}}
  ]
}}"""
