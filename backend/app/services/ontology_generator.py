"""
Ontology Generation Service
Interface 1: Analyze text content, generate entity and relationship type definitions suitable for social simulation
"""

from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger


# System Prompt for Ontology Generation
ONTOLOGY_SYSTEM_PROMPT = """You are a professional knowledge graph ontology design expert. Your task is to analyze the given text content and simulation requirements, and design entity types and relationship types suitable for **social media public opinion simulation**.

"**Important: You must output valid JSON format data, do not output any other content.**"

"## Core Task Background"

"We are building a **social media public opinion simulation system**. In this system:"
"- Each entity is an \"account\" or \"subject\" that can speak, interact, and spread information on social media"
"- Entities will influence each other, repost, comment, and respond"
"- We need to simulate the reactions of all parties in public opinion events and information dissemination paths"

"Therefore, **entities must be real subjects that exist in reality and can speak and interact on social media**:"

"**Can be**:"
"- Specific individuals (public figures, parties involved, opinion leaders, experts, scholars, ordinary people)"
"- Companies, enterprises (including their official accounts)"
"- Organizations (universities, associations, NGOs, unions, etc.)"
"- Government departments, regulatory agencies"
"- Media institutions (newspapers, TV stations, self-media, websites)"
"- Social media platforms themselves"
"- Representatives of specific groups (such as alumni associations, fan groups, rights protection groups, etc.)"

"**Cannot be**:"
"- Abstract concepts (such as \"public opinion\", \"emotion\", \"trend\")"
"- Topics/subjects (such as \"academic integrity\", \"education reform\")"
"- Opinions/attitudes (such as \"supporters\", \"opponents\")"

"## Output Format"

"Please output in JSON format, containing the following structure:"

```json
{
    "entity_types": [
        {
            "name": "Entity type name (English, PascalCase)",
            "description": "Brief description (English, no more than 100 characters)",
            "attributes": [
                {
                    "name": "Attribute name (English, snake_case)",
                    "type": "text",
                    "description": "Attribute description"
                }
            ],
            "examples": ["Example entity 1", "Example entity 2"]
        }
    ],
    "edge_types": [
        {
            "name": "Relationship type name (English, UPPER_SNAKE_CASE)",
            "description": "Brief description (English, no more than 100 characters)",
            "source_targets": [
                {"source": "Source entity type", "target": "Target entity type"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "Brief analysis of the text content (Chinese)"
}
```

## Design Guidelines (extremely important!)

### 1. Entity type design - Must be strictly followed

**Quantity requirement: Must be exactly 10 entity types**

**Hierarchy requirement (must include both specific types and fallback types)**:

Your 10 entity types must include the following hierarchy:

A. **Fallback types (must be included, placed as the last two in the list)**:
   - `Person`: Fallback type for any natural person. When a person does not belong to any more specific character type, they fall into this category.
   - `Organization`: Fallback type for any organization. When an organization does not belong to any more specific organization type, it falls into this category.

B. **Specific types (8, designed based on the text content)**:
   - Design more specific types for the main roles appearing in the text
   - For example: if the text involves academic events, there could be `Student`, `Professor`, `University`
   - For example: if the text involves business events, there could be `Company`, `CEO`, `Employee`

**Why fallback types are needed**:
- Various characters may appear in the text, such as "primary and secondary school teacher", "passerby A", "a certain netizen"
- If there is no specific type that matches, they should be classified into `Person`
- Likewise, small organizations, temporary groups, etc. should be classified into `Organization`

**Design principles for specific types**:
- Identify high-frequency or key role types from the text
- Each specific type should have clear boundaries to avoid overlap
- description must clearly explain the difference between this type and the fallback type

### 2. Relationship type design

- Quantity: 6-10
- Relationships should reflect real connections in social media interactions
- Ensure that the relationship's source_targets cover the entity types you defined

### 3. Attribute design

- 1-3 key attributes per entity type
- **Note**：attribute names cannot use `name`, `uuid`, `group_id`, `created_at`, `summary`（these are system reserved words）
- Recommended to use：`full_name`, `title`, `role`, `position`, `location`, `description` etc.

## Entity Type Reference

**Personal Class (Specific)**：
- Student: student
- Professor: professor/scholar
- Journalist: journalist
- Celebrity: celebrity/influencer
- Executive: executive
- Official: government official
- Lawyer: lawyer
- Doctor: doctor

**Personal Class (Fallback)**：
- Person: any natural person (used when not belonging to the above specific types)

**Organization Class (Specific)**：
- University: university
- Company: company enterprise
- GovernmentAgency: government agency
- MediaOutlet: media organization
- Hospital: hospital
- School: primary and secondary school
- NGO: non-governmental organization

**Organization Class (Fallback)**：
- Organization: any organization (used when not belonging to the above specific types)

## Relationship Type Reference

- WORKS_FOR: works at
- STUDIES_AT: studies at
- AFFILIATED_WITH: affiliated with
- REPRESENTS: represents
- REGULATES: regulates
- REPORTS_ON: Report
- COMMENTS_ON: Comments
- RESPONDS_TO: Responds
- SUPPORTS: Supports
- OPPOSES: Opposes
- COLLABORATES_WITH: Collaborates
- COMPETES_WITH: Competes
"""


class OntologyGenerator:
    """
    Ontology Generator
    Analyze text content, generate entity and relationship type definitions
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
        self.logger = get_logger('mirofish.ontology')
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate ontology definition
        
        Args:
            document_texts: Document text list
            simulation_requirement: Simulation requirement description
            additional_context: Additional context
            
        Returns:
            Ontology definition (entity_types, edge_types, etc.)
        """
        # Build user message
        user_message = self._build_user_message(
            document_texts, 
            simulation_requirement,
            additional_context
        )
        
        messages = [
            {"role": "system", "content": ONTOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        # Call LLM; if the local model cannot reliably return structured JSON, fall back to deterministic fallback ontology,
        # Avoid users failing after waiting several minutes due to empty response.
        try:
            result = self.llm_client.chat_json(
                messages=messages,
                temperature=0.3,
                max_tokens=8192
            )
        except Exception as exc:
            self.logger.warning("LLM ontology generation failed, using local fallback ontology: %s", str(exc))
            result = self._build_fallback_ontology(
                document_texts=document_texts,
                simulation_requirement=simulation_requirement,
                additional_context=additional_context,
                failure_reason=str(exc)
            )
        
        # Validate and post-process
        result = self._validate_and_process(result)
        
        return result
    
    # Maximum text length sent to LLM (50,000 characters)
    MAX_TEXT_LENGTH_FOR_LLM = 50000
    
    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """Build user message"""
        
        # Merge text
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)
        
        # If text exceeds 50,000 characters, truncate (only affects content sent to LLM, does not affect graph construction)
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(Original text total {original_length} characters, truncated first {self.MAX_TEXT_LENGTH_FOR_LLM} characters for ontology analysis)..."
        
        message = f"""## Simulation requirement

{simulation_requirement}

## Document content

{combined_text}
"""
        
        if additional_context:
            message += f"""
## Additional notes

{additional_context}
"""
        
        message += """
Please design entity types and relationship types suitable for social opinion simulation based on the above content.

**Rules that must be followed**:
1. Must output exactly 10 entity types
2. The last 2 must be fallback types: Person（personal fallback） and Organization（organizational fallback）
3. The first 8 are specific types designed based on the text content
4. All entity types must be real-world speaking entities, not abstract concepts
5. Attribute names cannot use reserved words like name, uuid, group_id, use full_name, org_name instead
"""
        
        return message

    def _infer_domain(self, text: str) -> str:
        """Based on keyword inference of scenario domain, for fallback ontology use."""
        text = (text or "").lower()
        domain_keywords = {
            "education": [
                "student", "students", "professor", "teacher", "campus", "university",
                "college", "school", "dorm", "curfew", "class", "faculty"
            ],
            "business": [
                "company", "employee", "employees", "ceo", "executive", "investor",
                "customer", "market", "startup", "corporate", "business"
            ],
            "healthcare": [
                "hospital", "patient", "patients", "doctor", "nurse", "clinic",
                "medical", "healthcare", "health", "public health"
            ],
            "public_affairs": [
                "government", "policy", "election", "minister", "regulation", "agency",
                "law", "police", "mayor", "parliament", "public"
            ],
        }
        scores = {
            domain: sum(text.count(keyword) for keyword in keywords)
            for domain, keywords in domain_keywords.items()
        }
        best_domain = max(scores, key=scores.get)
        return best_domain if scores[best_domain] > 0 else "generic"

    def _build_fallback_ontology(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str],
        failure_reason: str
    ) -> Dict[str, Any]:
        """When LLM cannot reliably return JSON, generate a usable conservative ontology."""
        combined_text = " ".join(document_texts or [])
        context_text = " ".join([
            simulation_requirement or "",
            additional_context or "",
            combined_text,
        ])
        domain = self._infer_domain(context_text)

        if domain == "education":
            entity_types = self._education_entities()
        elif domain == "business":
            entity_types = self._business_entities()
        elif domain == "healthcare":
            entity_types = self._healthcare_entities()
        elif domain == "public_affairs":
            entity_types = self._public_affairs_entities()
        else:
            entity_types = self._generic_entities()

        entity_names = [entity["name"] for entity in entity_types]
        edge_types = self._build_fallback_edges(entity_names)

        summary_map = {
            "education": "Detected education/school scenario, used education domain fallback ontology.",
            "business": "Detected business/company scenario, used business domain fallback ontology.",
            "healthcare": "Detected medical/public health scenario, used medical domain fallback ontology.",
            "public_affairs": "Detected public affairs/policy scenario, used public affairs fallback ontology.",
            "generic": "No clear vertical domain identified, used generic social opinion fallback ontology.",
        }

        return {
            "entity_types": entity_types,
            "edge_types": edge_types,
            "analysis_summary": (
                f"{summary_map.get(domain, summary_map['generic'])}"
                f"Reason: structured ontology generation failed ({failure_reason})."
            ),
        }

    def _education_entities(self) -> List[Dict[str, Any]]:
        return [
            self._entity("Student", "Students participating in the discussion.", ["full_name", "affiliation", "stance"]),
            self._entity("Professor", "Faculty members and academic experts.", ["full_name", "department", "position"]),
            self._entity("Administrator", "Campus administrators and policy decision makers.", ["full_name", "title", "office"]),
            self._entity("Journalist", "Individual reporters and commentators.", ["full_name", "outlet", "beat"]),
            self._entity("University", "Universities and colleges involved in the issue.", ["org_name", "location", "institution_type"]),
            self._entity("MediaOutlet", "Media organizations covering the issue.", ["org_name", "platform", "coverage_focus"]),
            self._entity("GovernmentAgency", "Public agencies supervising education or safety.", ["org_name", "jurisdiction", "agency_type"]),
            self._entity("AdvocacyGroup", "Student groups, parent groups, or civic advocates.", ["org_name", "focus_area", "constituency"]),
            self._entity("Person", "Any individual person not fitting other specific person types.", ["full_name", "role"]),
            self._entity("Organization", "Any organization not fitting other specific organization types.", ["org_name", "org_type"]),
        ]

    def _business_entities(self) -> List[Dict[str, Any]]:
        return [
            self._entity("Employee", "Employees directly affected by the issue.", ["full_name", "job_title", "team"]),
            self._entity("Executive", "Senior executives and company leaders.", ["full_name", "position", "company_affiliation"]),
            self._entity("Customer", "Customers and end users reacting publicly.", ["full_name", "segment", "location"]),
            self._entity("Journalist", "Individual reporters and commentators.", ["full_name", "outlet", "beat"]),
            self._entity("Company", "Companies and business entities involved.", ["org_name", "industry", "location"]),
            self._entity("MediaOutlet", "Media organizations covering the issue.", ["org_name", "platform", "coverage_focus"]),
            self._entity("GovernmentAgency", "Regulators and public oversight bodies.", ["org_name", "jurisdiction", "agency_type"]),
            self._entity("AdvocacyGroup", "Labor groups, consumer groups, or activists.", ["org_name", "focus_area", "constituency"]),
            self._entity("Person", "Any individual person not fitting other specific person types.", ["full_name", "role"]),
            self._entity("Organization", "Any organization not fitting other specific organization types.", ["org_name", "org_type"]),
        ]

    def _healthcare_entities(self) -> List[Dict[str, Any]]:
        return [
            self._entity("Patient", "Patients or family members discussing the issue.", ["full_name", "location", "concern"]),
            self._entity("Doctor", "Doctors and physician experts.", ["full_name", "specialty", "institution"]),
            self._entity("Nurse", "Nurses and frontline healthcare staff.", ["full_name", "department", "institution"]),
            self._entity("Journalist", "Individual reporters and commentators.", ["full_name", "outlet", "beat"]),
            self._entity("Hospital", "Hospitals and medical institutions involved.", ["org_name", "location", "facility_type"]),
            self._entity("MediaOutlet", "Media organizations covering the issue.", ["org_name", "platform", "coverage_focus"]),
            self._entity("GovernmentAgency", "Public health regulators and agencies.", ["org_name", "jurisdiction", "agency_type"]),
            self._entity("AdvocacyGroup", "Patient groups and civic organizations.", ["org_name", "focus_area", "constituency"]),
            self._entity("Person", "Any individual person not fitting other specific person types.", ["full_name", "role"]),
            self._entity("Organization", "Any organization not fitting other specific organization types.", ["org_name", "org_type"]),
        ]

    def _public_affairs_entities(self) -> List[Dict[str, Any]]:
        return [
            self._entity("Official", "Government officials and spokespersons.", ["full_name", "position", "jurisdiction"]),
            self._entity("Citizen", "Residents and individual members of the public.", ["full_name", "location", "stance"]),
            self._entity("Journalist", "Individual reporters and commentators.", ["full_name", "outlet", "beat"]),
            self._entity("Activist", "Organizers, advocates, and movement leaders.", ["full_name", "cause", "affiliation"]),
            self._entity("GovernmentAgency", "Public institutions and regulatory bodies.", ["org_name", "jurisdiction", "agency_type"]),
            self._entity("MediaOutlet", "Media organizations covering the issue.", ["org_name", "platform", "coverage_focus"]),
            self._entity("Platform", "Social media platforms or online communities involved.", ["org_name", "platform_type", "audience"]),
            self._entity("NGO", "Nonprofits, unions, or advocacy organizations.", ["org_name", "focus_area", "constituency"]),
            self._entity("Person", "Any individual person not fitting other specific person types.", ["full_name", "role"]),
            self._entity("Organization", "Any organization not fitting other specific organization types.", ["org_name", "org_type"]),
        ]

    def _generic_entities(self) -> List[Dict[str, Any]]:
        return [
            self._entity("Participant", "Individuals actively discussing the issue online.", ["full_name", "role", "stance"]),
            self._entity("Expert", "Experts, analysts, or commentators.", ["full_name", "specialty", "affiliation"]),
            self._entity("Journalist", "Individual reporters and commentators.", ["full_name", "outlet", "beat"]),
            self._entity("Creator", "Influencers, creators, or community leaders.", ["full_name", "channel", "audience"]),
            self._entity("Institution", "Named institutions central to the issue.", ["org_name", "institution_type", "location"]),
            self._entity("MediaOutlet", "Media organizations covering the issue.", ["org_name", "platform", "coverage_focus"]),
            self._entity("Platform", "Social platforms or online communities involved.", ["org_name", "platform_type", "audience"]),
            self._entity("AdvocacyGroup", "Communities, nonprofits, or organized groups.", ["org_name", "focus_area", "constituency"]),
            self._entity("Person", "Any individual person not fitting other specific person types.", ["full_name", "role"]),
            self._entity("Organization", "Any organization not fitting other specific organization types.", ["org_name", "org_type"]),
        ]

    def _entity(self, name: str, description: str, attrs: List[str]) -> Dict[str, Any]:
        attr_descriptions = {
            "full_name": "Full name of the individual",
            "affiliation": "Primary affiliation of the individual",
            "stance": "Typical stance in the public discussion",
            "department": "Department or academic unit",
            "position": "Formal role or position",
            "office": "Office or administrative unit",
            "outlet": "Media outlet or publication",
            "beat": "Primary coverage beat",
            "org_name": "Name of the organization",
            "location": "Primary location",
            "institution_type": "Type of institution",
            "platform": "Primary platform or channel",
            "coverage_focus": "Main area of coverage",
            "jurisdiction": "Jurisdiction or scope of authority",
            "agency_type": "Type of agency",
            "focus_area": "Primary focus area",
            "constituency": "Main community represented",
            "job_title": "Primary job title",
            "team": "Team or division",
            "company_affiliation": "Company the executive is associated with",
            "segment": "Customer segment or audience segment",
            "industry": "Industry or sector",
            "facility_type": "Type of healthcare facility",
            "concern": "Primary concern being discussed",
            "specialty": "Professional specialty",
            "institution": "Institutional affiliation",
            "cause": "Primary cause or campaign",
            "platform_type": "Type of platform",
            "audience": "Primary audience served",
            "channel": "Main channel or account type",
            "role": "Role or occupation",
            "org_type": "Type of organization",
        }
        return {
            "name": name,
            "description": description[:100],
            "attributes": [
                {
                    "name": attr,
                    "type": "text",
                    "description": attr_descriptions.get(attr, attr.replace("_", " "))
                }
                for attr in attrs[:3]
            ],
            "examples": []
        }

    def _build_fallback_edges(self, entity_names: List[str]) -> List[Dict[str, Any]]:
        all_pairs = self._pairs(entity_names, entity_names)
        person_like = [name for name in entity_names if name not in {"University", "Company", "Hospital", "GovernmentAgency", "MediaOutlet", "AdvocacyGroup", "NGO", "Institution", "Platform", "Organization"}]
        org_like = [name for name in entity_names if name not in {"Student", "Professor", "Administrator", "Journalist", "Employee", "Executive", "Customer", "Patient", "Doctor", "Nurse", "Official", "Citizen", "Activist", "Participant", "Expert", "Creator", "Person"}]
        education_orgs = [name for name in entity_names if name in {"University", "School", "Institution", "Organization"}]

        edges = [
            self._edge("AFFILIATED_WITH", "Entity is affiliated with an organization.", self._pairs(person_like, org_like)),
            self._edge("WORKS_FOR", "Person or role works for an organization.", self._pairs(person_like, org_like)),
            self._edge("STUDIES_AT", "Learner studies at an educational institution.", self._pairs(["Student"], education_orgs)),
            self._edge("REPORTS_ON", "Media actor reports on a target entity or issue actor.", self._pairs(["Journalist", "MediaOutlet"], entity_names)),
            self._edge("RESPONDS_TO", "Actor publicly responds to another actor.", all_pairs),
            self._edge("SUPPORTS", "Actor publicly supports another actor or organization.", all_pairs),
            self._edge("OPPOSES", "Actor publicly opposes another actor or organization.", all_pairs),
            self._edge("REPRESENTS", "Actor speaks on behalf of a group or institution.", self._pairs(person_like, org_like)),
        ]

        return [edge for edge in edges if edge["source_targets"]]

    def _edge(self, name: str, description: str, pairs: List[Dict[str, str]]) -> Dict[str, Any]:
        return {
            "name": name,
            "description": description[:100],
            "source_targets": pairs[:40],
            "attributes": []
        }

    def _pairs(self, sources: List[str], targets: List[str]) -> List[Dict[str, str]]:
        deduped = []
        seen = set()
        for source in sources:
            for target in targets:
                if source and target:
                    key = (source, target)
                    if key not in seen:
                        seen.add(key)
                        deduped.append({"source": source, "target": target})
        return deduped
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and post-process results"""
        
        # Ensure required fields exist
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""
        
        # Validate entity types
        for entity in result["entity_types"]:
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # Ensure description does not exceed 100 characters
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."
        
        # Validate relationship types
        for edge in result["edge_types"]:
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
        
        # Zep API limits: up to 10 custom entity types, up to 10 custom edge types
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10
        
        # Fallback type definitions
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary citizen", "anonymous netizen"]
        }
        
        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "community group"]
        }
        
        # Check if fallback types already exist
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names
        
        # Fallback types to add
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)
        
        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)
            
            # If adding would exceed 10, need to remove some existing types
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                # Calculate how many to remove
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # Remove from the end (keep earlier more important specific types)
                result["entity_types"] = result["entity_types"][:-to_remove]
            
            # Add fallback types
            result["entity_types"].extend(fallbacks_to_add)
        
        # Finally ensure not exceeding limits (defensive programming)
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]
        
        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]
        
        return result
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        Convert ontology definition to Python code (similar to ontology.py)
        
        Args:
            ontology: ontology definition
            
        Returns:
            Python code string
        """
        code_lines = [
            '"""',
            'Custom entity type definitions',
            'Generated automatically by MiroFish, used for social opinion simulation',
            '"""',
            '',
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
            '',
            '# ============== Entity type definition ==============',
            '',
        ]
        
        # Generate entity types
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")
            
            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== Relationship type definition ==============')
        code_lines.append('')
        
        # Generate relationship types
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # Convert to PascalCase class name
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")
            
            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        # Generate type dictionary
        code_lines.append('# ============== Type configuration ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')
        
        # Generate source_targets mapping of edges
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)
