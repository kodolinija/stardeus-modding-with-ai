// Runs dnSpy.Console in this process after giving it a console of its own. dnSpy.Console sets
// Console.OutputEncoding first thing, which throws "The handle is invalid" when there is no
// console, as under an AI agent's shell where output goes to a pipe.
// Usage: DnSpyHost <folder with dnSpy.Console.dll> <dnSpy.Console arguments...>
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;

static class Program {
    [DllImport("kernel32.dll")]
    private static extern bool AllocConsole();

    [DllImport("kernel32.dll")]
    private static extern IntPtr GetConsoleWindow();

    [DllImport("user32.dll")]
    private static extern bool ShowWindow(IntPtr window, int command);

    private static int Main(string[] args) {
        if (args.Length < 2) {
            Console.Error.WriteLine("Usage: DnSpyHost <dnSpy folder> <dnSpy.Console arguments...>");
            return 2;
        }
        var dir = args[0];
        if (AllocConsole()) {
            var window = GetConsoleWindow();
            if (window != IntPtr.Zero) {
                ShowWindow(window, 0);
            }
        }
        AppDomain.CurrentDomain.AssemblyResolve += (s, e) => {
            var path = Path.Combine(dir, new AssemblyName(e.Name).Name + ".dll");
            return File.Exists(path) ? Assembly.LoadFrom(path) : null;
        };
        var asm = Assembly.LoadFrom(Path.Combine(dir, "dnSpy.Console.dll"));
        var main = asm.GetType("dnSpy_Console.Program")
            .GetMethod("Main", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);
        var result = main.Invoke(null, new object[] { args.Skip(1).ToArray() });
        return result is int code ? code : 0;
    }
}
