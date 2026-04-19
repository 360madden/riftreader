using System.Reflection;

namespace RiftReader.WorkflowHud;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        ApplicationConfiguration.Initialize();
        var options = WorkflowHudOptions.Parse(args);
        Application.Run(new WorkflowHudForm(options, BuildVersionLabel()));
    }

    private static string BuildVersionLabel()
    {
        const string utilityName = "RiftReader Workflow HUD";
        var assembly = Assembly.GetExecutingAssembly();
        var informationalVersion = assembly
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>()?
            .InformationalVersion?
            .Split('+', 2)[0];

        var versionText = !string.IsNullOrWhiteSpace(informationalVersion)
            ? informationalVersion
            : assembly.GetName().Version?.ToString(3) ?? "0.0.0";

        return $"{utilityName} v{versionText}";
    }
}
