// Copyright Epic Games, Inc. All Rights Reserved.
/*===========================================================================
	Generated code exported from UnrealHeaderTool.
	DO NOT modify this manually! Edit the corresponding .h files instead!
===========================================================================*/

// IWYU pragma: private, include "NaniteAssemblySkeletalMeshBuilder.h"

#ifdef NANITEASSEMBLYEDITORUTILS_NaniteAssemblySkeletalMeshBuilder_generated_h
#error "NaniteAssemblySkeletalMeshBuilder.generated.h already included, missing '#pragma once' in NaniteAssemblySkeletalMeshBuilder.h"
#endif
#define NANITEASSEMBLYEDITORUTILS_NaniteAssemblySkeletalMeshBuilder_generated_h

#include "UObject/ObjectMacros.h"
#include "UObject/ScriptMacros.h"

PRAGMA_DISABLE_DEPRECATION_WARNINGS
class UNaniteAssemblySkeletalMeshBuilder;
class USkeletalMesh;
enum class ENaniteAssemblyNodeTransformSpace : uint8;
struct FNaniteAssemblyCreateNewParameters;
struct FNaniteAssemblyMaterialMergeOptions;
struct FNaniteAssemblySkeletalMeshPartBinding;

// ********** Begin Class UNaniteAssemblySkeletalMeshBuilder ***************************************
#define FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblySkeletalMeshBuilder_h_16_RPC_WRAPPERS_NO_PURE_DECLS \
	DECLARE_FUNCTION(execAddBoneInfluenceByName); \
	DECLARE_FUNCTION(execCreateBindingBySocketName); \
	DECLARE_FUNCTION(execCreateBindingByBoneName); \
	DECLARE_FUNCTION(execAddAssemblyPart); \
	DECLARE_FUNCTION(execAddAssemblyParts); \
	DECLARE_FUNCTION(execFinishAssemblyBuild); \
	DECLARE_FUNCTION(execBeginEditSkeletalMeshAssemblyBuild); \
	DECLARE_FUNCTION(execBeginNewSkeletalMeshAssemblyBuild);


struct Z_Construct_UClass_UNaniteAssemblySkeletalMeshBuilder_Statics;
NANITEASSEMBLYEDITORUTILS_API UClass* Z_Construct_UClass_UNaniteAssemblySkeletalMeshBuilder_NoRegister();

#define FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblySkeletalMeshBuilder_h_16_INCLASS_NO_PURE_DECLS \
private: \
	static void StaticRegisterNativesUNaniteAssemblySkeletalMeshBuilder(); \
	friend struct ::Z_Construct_UClass_UNaniteAssemblySkeletalMeshBuilder_Statics; \
	static UClass* GetPrivateStaticClass(); \
	friend NANITEASSEMBLYEDITORUTILS_API UClass* ::Z_Construct_UClass_UNaniteAssemblySkeletalMeshBuilder_NoRegister(); \
public: \
	DECLARE_CLASS2(UNaniteAssemblySkeletalMeshBuilder, UNaniteAssemblyBuilder, COMPILED_IN_FLAGS(0), CASTCLASS_None, TEXT("/Script/NaniteAssemblyEditorUtils"), Z_Construct_UClass_UNaniteAssemblySkeletalMeshBuilder_NoRegister) \
	DECLARE_SERIALIZER(UNaniteAssemblySkeletalMeshBuilder)


#define FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblySkeletalMeshBuilder_h_16_ENHANCED_CONSTRUCTORS \
	/** Deleted move- and copy-constructors, should never be used */ \
	UNaniteAssemblySkeletalMeshBuilder(UNaniteAssemblySkeletalMeshBuilder&&) = delete; \
	UNaniteAssemblySkeletalMeshBuilder(const UNaniteAssemblySkeletalMeshBuilder&) = delete; \
	DECLARE_VTABLE_PTR_HELPER_CTOR(NO_API, UNaniteAssemblySkeletalMeshBuilder); \
	DEFINE_VTABLE_PTR_HELPER_CTOR_CALLER(UNaniteAssemblySkeletalMeshBuilder); \
	DEFINE_DEFAULT_OBJECT_INITIALIZER_CONSTRUCTOR_CALL(UNaniteAssemblySkeletalMeshBuilder) \
	NO_API virtual ~UNaniteAssemblySkeletalMeshBuilder();


#define FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblySkeletalMeshBuilder_h_13_PROLOG
#define FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblySkeletalMeshBuilder_h_16_GENERATED_BODY \
PRAGMA_DISABLE_DEPRECATION_WARNINGS \
public: \
	FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblySkeletalMeshBuilder_h_16_RPC_WRAPPERS_NO_PURE_DECLS \
	FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblySkeletalMeshBuilder_h_16_INCLASS_NO_PURE_DECLS \
	FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblySkeletalMeshBuilder_h_16_ENHANCED_CONSTRUCTORS \
private: \
PRAGMA_ENABLE_DEPRECATION_WARNINGS


class UNaniteAssemblySkeletalMeshBuilder;

// ********** End Class UNaniteAssemblySkeletalMeshBuilder *****************************************

#undef CURRENT_FILE_ID
#define CURRENT_FILE_ID FID_Engine_Plugins_Experimental_NaniteAssemblyEditorUtils_Source_NaniteAssemblyEditorUtils_Public_NaniteAssemblySkeletalMeshBuilder_h

PRAGMA_ENABLE_DEPRECATION_WARNINGS
