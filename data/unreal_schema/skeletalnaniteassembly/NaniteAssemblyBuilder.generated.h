// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

// IWYU pragma: private, include "NaniteAssemblyBuilder.h"

#ifdef NANITEASSEMBLYEDITORUTILS_NaniteAssemblyBuilder_generated_h
#error "NaniteAssemblyBuilder.generated.h already included, missing '#pragma once' in NaniteAssemblyBuilder.h"
#endif
#define NANITEASSEMBLYEDITORUTILS_NaniteAssemblyBuilder_generated_h

#include "UObject/ObjectMacros.h"
#include "UObject/ScriptMacros.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
class UMaterialInterface;
class UObject;

// ********** Begin ScriptStruct FNaniteAssemblyMaterialMergeOptions *******************************
struct Z_Construct_UScriptStruct_FNaniteAssemblyMaterialMergeOptions_Statics;
#define FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblyBuilder_h_33_GENERATED_BODY \
	friend struct ::Z_Construct_UScriptStruct_FNaniteAssemblyMaterialMergeOptions_Statics; \
	NANITEASSEMBLYEDITORUTILS_API static class UScriptStruct* StaticStruct();


struct FNaniteAssemblyMaterialMergeOptions;
// ********** End ScriptStruct FNaniteAssemblyMaterialMergeOptions *********************************

// ********** Begin ScriptStruct FNaniteAssemblyCreateNewParameters ********************************
struct Z_Construct_UScriptStruct_FNaniteAssemblyCreateNewParameters_Statics;
#define FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblyBuilder_h_58_GENERATED_BODY \
	friend struct ::Z_Construct_UScriptStruct_FNaniteAssemblyCreateNewParameters_Statics; \
	NANITEASSEMBLYEDITORUTILS_API static class UScriptStruct* StaticStruct();


struct FNaniteAssemblyCreateNewParameters;
// ********** End ScriptStruct FNaniteAssemblyCreateNewParameters **********************************

// ********** Begin ScriptStruct FNaniteAssemblySkeletalMeshPartBinding ****************************
struct Z_Construct_UScriptStruct_FNaniteAssemblySkeletalMeshPartBinding_Statics;
#define FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblyBuilder_h_79_GENERATED_BODY \
	friend struct ::Z_Construct_UScriptStruct_FNaniteAssemblySkeletalMeshPartBinding_Statics; \
	NANITEASSEMBLYEDITORUTILS_API static class UScriptStruct* StaticStruct();


struct FNaniteAssemblySkeletalMeshPartBinding;
// ********** End ScriptStruct FNaniteAssemblySkeletalMeshPartBinding ******************************

// ********** Begin Class UNaniteAssemblyBuilder ***************************************************
#define FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblyBuilder_h_97_RPC_WRAPPERS_NO_PURE_DECLS \
	DECLARE_FUNCTION(execAddMaterialSlot); \
	DECLARE_FUNCTION(execAddMaterialSlotGroup); \
	DECLARE_FUNCTION(execIsBuildingAssembly); \
	DECLARE_FUNCTION(execGetTargetMeshObject);


struct Z_Construct_UClass_UNaniteAssemblyBuilder_Statics;
NANITEASSEMBLYEDITORUTILS_API UClass* Z_Construct_UClass_UNaniteAssemblyBuilder_NoRegister();

#define FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblyBuilder_h_97_INCLASS_NO_PURE_DECLS \
private: \
	static void StaticRegisterNativesUNaniteAssemblyBuilder(); \
	friend struct ::Z_Construct_UClass_UNaniteAssemblyBuilder_Statics; \
	static UClass* GetPrivateStaticClass(); \
	friend NANITEASSEMBLYEDITORUTILS_API UClass* ::Z_Construct_UClass_UNaniteAssemblyBuilder_NoRegister(); \
public: \
	DECLARE_CLASS2(UNaniteAssemblyBuilder, UObject, COMPILED_IN_FLAGS(CLASS_Abstract), CASTCLASS_None, TEXT("/Script/NaniteAssemblyEditorUtils"), Z_Construct_UClass_UNaniteAssemblyBuilder_NoRegister) \
	DECLARE_SERIALIZER(UNaniteAssemblyBuilder)


#define FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblyBuilder_h_97_ENHANCED_CONSTRUCTORS \
	/** Deleted move- and copy-constructors, should never be used */ \
	UNaniteAssemblyBuilder(UNaniteAssemblyBuilder&&) = delete; \
	UNaniteAssemblyBuilder(const UNaniteAssemblyBuilder&) = delete; \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, UNaniteAssemblyBuilder); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(UNaniteAssemblyBuilder); \
	DEFINE_ABSTRACT_DEFAULT_OBJECT_INITIALIZER_CONSTRUCTOR_CALL(UNaniteAssemblyBuilder) \
	NO_API virtual ~UNaniteAssemblyBuilder();


#define FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblyBuilder_h_94_PROLOG
#define FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblyBuilder_h_97_GENERATED_BODY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblyBuilder_h_97_RPC_WRAPPERS_NO_PURE_DECLS \
	FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblyBuilder_h_97_INCLASS_NO_PURE_DECLS \
	FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblyBuilder_h_97_ENHANCED_CONSTRUCTORS \
private: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


class UNaniteAssemblyBuilder;

// ********** End Class UNaniteAssemblyBuilder *****************************************************

#undef CURRENT_FILE_ID
#define CURRENT_FILE_ID FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblyBuilder_h

// ********** Begin Enum ENaniteAssemblyPartMaterialMerge ******************************************
#define FOREACH_ENUM_ENANITEASSEMBLYPARTMATERIALMERGE(op) \
	op(ENaniteAssemblyPartMaterialMerge::MergeIdenticalMaterials) \
	op(ENaniteAssemblyPartMaterialMerge::MergeIdenticalSlotNames) \
	op(ENaniteAssemblyPartMaterialMerge::MergeMaterialIndices) 

enum class ENaniteAssemblyPartMaterialMerge : uint8;
template<> struct TIsUEnumClass<ENaniteAssemblyPartMaterialMerge> { enum { Value = true }; };
template<> NANITEASSEMBLYEDITORUTILS_NON_ATTRIBUTED_API UEnum* StaticEnum<ENaniteAssemblyPartMaterialMerge>();
// ********** End Enum ENaniteAssemblyPartMaterialMerge ********************************************

PRAGMA_ENABLE_DEPRECATION_WARNINGS
