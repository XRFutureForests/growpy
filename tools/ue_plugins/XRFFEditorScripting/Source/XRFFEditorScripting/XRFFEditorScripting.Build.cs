using UnrealBuildTool;

public class XRFFEditorScripting : ModuleRules
{
	public XRFFEditorScripting(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "BlueprintGraph" });
		PrivateDependencyModuleNames.AddRange(new string[] { "UnrealEd", "Kismet", "KismetCompiler", "AssetRegistry", "AssetTools", "UMG", "UMGEditor", "Landscape",
			"PCG", "ProceduralVegetation", "Chaos" });  // XRFF-655 PVE skeleton dump
	}
}
