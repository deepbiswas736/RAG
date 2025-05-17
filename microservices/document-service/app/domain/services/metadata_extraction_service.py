    async def process_metadata(self, document_id: str, content: str) -> Dict[str, Any]:
        """
        Process document metadata with enhanced validation and error handling
        
        Args:
            document_id: Document ID
            content: Document content
            
        Returns:
            Extracted and validated metadata
        """
        try:
            # First pass: Extract basic metadata
            metadata = self._extract_basic_metadata(content)
            
            # Second pass: Enhanced metadata with LLM
            enhanced_metadata = await self._enhance_metadata_with_llm(content, metadata)
            
            # Validate metadata
            validated_metadata = self._validate_metadata(enhanced_metadata)
            
            # Add document ID
            validated_metadata["document_id"] = document_id
            
            # Add metadata quality metrics
            validated_metadata["metadata_quality"] = self._calculate_metadata_quality(validated_metadata)
            
            return validated_metadata
            
        except Exception as e:
            logger.error(f"Error processing metadata for document {document_id}: {e}")
            return {
                "document_id": document_id,
                "error": str(e),
                "metadata_quality": 0.0
            }
            
    def _extract_basic_metadata(self, content: str) -> Dict[str, Any]:
        """Extract basic metadata using pattern matching and rules"""
        metadata = {
            "word_count": len(content.split()),
            "char_count": len(content),
            "language": self._detect_language(content),
            "content_type": self._detect_content_type(content)
        }
        
        # Extract potential keywords
        metadata["keywords"] = self._extract_keywords(content)
        
        # Extract dates
        metadata["dates"] = self._extract_dates(content)
        
        return metadata
        
    def _validate_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean metadata"""
        validated = {}
        
        # Validate and clean each field
        for field, value in metadata.items():
            # Skip null or empty values
            if value is None or (isinstance(value, (str, list, dict)) and not value):
                continue
                
            # Validate lists (topics, keywords, etc.)
            if isinstance(value, list):
                # Remove duplicates and empty items
                cleaned = list(set(str(item).strip() for item in value if item))
                # Only keep if we have valid items
                if cleaned:
                    validated[field] = cleaned
                    
            # Validate dictionaries (entities, etc.)
            elif isinstance(value, dict):
                cleaned = {k: v for k, v in value.items() if v is not None and v != {}}
                if cleaned:
                    validated[field] = cleaned
                    
            # Validate strings
            elif isinstance(value, str):
                cleaned = value.strip()
                if cleaned:
                    validated[field] = cleaned
                    
            # Keep other types as is (numbers, booleans)
            else:
                validated[field] = value
                
        return validated
        
    def _calculate_metadata_quality(self, metadata: Dict[str, Any]) -> float:
        """Calculate a quality score for the metadata"""
        quality_score = 0.0
        weights = {
            "keywords": 0.2,
            "topics": 0.2,
            "entities": 0.2,
            "summary": 0.2,
            "language": 0.1,
            "content_type": 0.1
        }
        
        for field, weight in weights.items():
            if field in metadata:
                value = metadata[field]
                if isinstance(value, list):
                    # Score based on number of items (up to 5)
                    quality_score += weight * min(len(value) / 5.0, 1.0)
                elif isinstance(value, dict):
                    # Score based on number of non-empty fields
                    quality_score += weight * min(len(value) / 3.0, 1.0)
                elif isinstance(value, str):
                    # Score based on string length
                    quality_score += weight * (1.0 if value else 0.0)
                    
        return round(quality_score, 2)
        
    async def _enhance_metadata_with_llm(self, content: str, basic_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Enhance metadata using LLM analysis"""
        try:
            # Create analysis prompt
            prompt = self._create_metadata_analysis_prompt(content, basic_metadata)
            
            # Get LLM response
            llm_response = await self.llm_manager.generate_response(prompt, [])
            
            # Parse and validate LLM response
            llm_metadata = self._parse_llm_metadata_response(llm_response)
            
            if not llm_metadata:
                logger.warning("LLM metadata extraction failed, using basic metadata only")
                return basic_metadata
                
            # Combine basic and LLM metadata
            enhanced_metadata = {**basic_metadata, **llm_metadata}
            
            return enhanced_metadata
            
        except Exception as e:
            logger.error(f"Error enhancing metadata with LLM: {e}")
            return basic_metadata