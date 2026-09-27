// Iniciar Probador.exe — arranca el proyecto con un doble clic.
//
// NO EMPAQUETA LA APLICACIÓN
// --------------------------
// La regla 10 del proyecto sigue en pie: es una aplicación web. Este programa
// no la contiene; hace lo que harían dos terminales y un navegador:
//
//   1. arranca el backend (start-backend.ps1) y el frontend (start-frontend.ps1),
//      sin ventanas, con su salida en logs\backend.log y logs\frontend.log;
//   2. espera a que los dos respondan;
//   3. abre http://localhost:5173 en el navegador;
//   4. al cerrar su ventana (o pulsar Enter), APAGA los dos.
//
// Lo cuarto es lo que no se consigue con un .bat: si alguien cierra la ventana
// con la X, los servidores se quedarían vivos ocupando los puertos, y el
// siguiente arranque fallaría con «el puerto ya está en uso». Aquí los dos
// servidores —y todo lo que ellos arranquen, como el proceso de recarga de
// uvicorn— van dentro de un «job» de Windows marcado para morir cuando se
// cierre: el sistema los termina aunque este programa muera de golpe.
//
// Cada servidor se crea SUSPENDIDO, se mete en el job y solo entonces se
// reanuda. Si se metiera después de arrancar, los procesos que alcanzara a
// crear en ese intervalo quedarían fuera del job, y huérfanos al cerrar.
//
// Se compila con el compilador de C# que trae Windows (.NET Framework 4), sin
// instalar nada: lanzador\compilar.ps1. Por eso el código es C# 5.

using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

internal static class IniciarProbador
{
    private const string Aplicacion = "http://localhost:5173";
    private const string Salud = "http://127.0.0.1:8000/api/health";
    private const int PuertoBackend = 8000;
    private const int PuertoFrontend = 5173;
    private const int PuertoPostgres = 5432;

    // La primera vez, el frontend instala sus dependencias antes de arrancar.
    private const int EsperaMaximaSegundos = 240;

    private static IntPtr trabajo = IntPtr.Zero;

    private static int Main(string[] args)
    {
        Console.OutputEncoding = Encoding.UTF8;
        Console.Title = "Probador Virtual";

        string raiz = AppDomain.CurrentDomain.BaseDirectory;
        string scriptBackend = Path.Combine(raiz, "start-backend.ps1");
        string scriptFrontend = Path.Combine(raiz, "start-frontend.ps1");
        if (!File.Exists(scriptBackend) || !File.Exists(scriptFrontend))
        {
            Error("No encuentro start-backend.ps1 y start-frontend.ps1 junto a este programa.",
                  "Tiene que estar en la carpeta raíz del proyecto: " + raiz);
            return Salir(1);
        }

        bool abrirNavegador = Array.IndexOf(args, "--sin-navegador") < 0;
        string logs = Path.Combine(raiz, "logs");
        Directory.CreateDirectory(logs);

        Titulo();

        if (!PuertoAbierto(PuertoPostgres))
        {
            Aviso("PostgreSQL no responde en el puerto 5432.",
                  "La aplicación arrancará, pero sin base de datos no funcionará. Arranca el servicio",
                  "«postgresql-x64-16» (Servicios de Windows), o «docker compose up -d» si usas Docker.");
        }

        CrearTrabajo();

        string logBackend = Path.Combine(logs, "backend.log");
        string logFrontend = Path.Combine(logs, "frontend.log");

        if (PuertoAbierto(PuertoBackend))
            Linea("Backend", "ya estaba en marcha en el puerto 8000; se usa ese.");
        else
            Arrancar(scriptBackend, logBackend, raiz, "Backend");

        if (PuertoAbierto(PuertoFrontend))
            Linea("Frontend", "ya estaba en marcha en el puerto 5173; se usa ese.");
        else
            Arrancar(scriptFrontend, logFrontend, raiz, "Frontend");

        Console.WriteLine();
        Console.Write("  Esperando a que respondan");

        string salud = null;
        DateTime limite = DateTime.Now.AddSeconds(EsperaMaximaSegundos);
        bool frontendListo = false;
        while (DateTime.Now < limite && (salud == null || !frontendListo))
        {
            if (salud == null) salud = PedirSalud();
            if (!frontendListo) frontendListo = PuertoAbierto(PuertoFrontend);
            if (salud == null || !frontendListo)
            {
                Console.Write(".");
                Thread.Sleep(1000);
            }
        }
        Console.WriteLine();
        Console.WriteLine();

        if (salud == null)
        {
            Error("El backend no ha respondido en " + EsperaMaximaSegundos + " s. Lo último que escribió:");
            MostrarFinal(logBackend);
            return Salir(1);
        }
        if (!frontendListo)
        {
            Error("El frontend no ha respondido en " + EsperaMaximaSegundos + " s. Lo último que escribió:");
            MostrarFinal(logFrontend);
            return Salir(1);
        }

        Linea("Backend", "listo en http://localhost:8000 (documentación en /docs)");
        Linea("Frontend", "listo en " + Aplicacion);
        if (salud.Contains("\"database\":\"down\""))
        {
            Console.WriteLine();
            Aviso("El backend responde, pero dice que la base de datos está caída.",
                  "Arranca PostgreSQL y recarga la página.");
        }

        if (abrirNavegador)
        {
            try
            {
                Process.Start(Aplicacion);
            }
            catch (Exception)
            {
                Linea("Navegador", "no se pudo abrir solo; entra tú en " + Aplicacion);
            }
        }

        Console.WriteLine();
        Console.ForegroundColor = ConsoleColor.Green;
        Console.WriteLine("  Todo en marcha. Deja esta ventana abierta mientras uses la aplicación.");
        Console.ResetColor();
        Console.WriteLine("  Para apagarlo todo: pulsa Enter, o cierra esta ventana.");
        Console.WriteLine("  Registros: " + logs);
        Console.ReadLine();

        Console.WriteLine("  Apagando…");
        CerrarTrabajo();
        return 0;
    }

    // --- Arranque de los servidores dentro del job -------------------------------

    private static void Arrancar(string script, string log, string carpeta, string nombre)
    {
        // cmd hace la redirección a archivo; powershell ejecuta el script con
        // la política de ejecución relajada solo para esta llamada.
        string orden = "cmd.exe /d /c powershell -NoProfile -ExecutionPolicy Bypass -File \"" +
                       script + "\" > \"" + log + "\" 2>&1";

        var inicio = new STARTUPINFO();
        inicio.cb = Marshal.SizeOf(typeof(STARTUPINFO));
        PROCESS_INFORMATION proceso;
        bool creado = CreateProcess(null, new StringBuilder(orden), IntPtr.Zero, IntPtr.Zero, false,
                                    CREATE_SUSPENDED | CREATE_NO_WINDOW, IntPtr.Zero, carpeta,
                                    ref inicio, out proceso);
        if (!creado)
        {
            Error("No se pudo arrancar " + nombre + " (error de Windows " + Marshal.GetLastWin32Error() + ").");
            return;
        }
        if (trabajo != IntPtr.Zero && !AssignProcessToJobObject(trabajo, proceso.hProcess))
        {
            Aviso(nombre + " arrancará, pero no se podrá apagar solo al cerrar esta ventana.",
                  "Ciérralo desde el Administrador de tareas si hace falta.");
        }
        ResumeThread(proceso.hThread);
        CloseHandle(proceso.hThread);
        CloseHandle(proceso.hProcess);
        Linea(nombre, "arrancando… (registro en logs\\" + Path.GetFileName(log) + ")");
    }

    private static void CrearTrabajo()
    {
        trabajo = CreateJobObject(IntPtr.Zero, null);
        if (trabajo == IntPtr.Zero) return;

        var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        int tamano = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
        IntPtr puntero = Marshal.AllocHGlobal(tamano);
        try
        {
            Marshal.StructureToPtr(info, puntero, false);
            if (!SetInformationJobObject(trabajo, JobObjectExtendedLimitInformation, puntero, (uint)tamano))
            {
                CloseHandle(trabajo);
                trabajo = IntPtr.Zero;
            }
        }
        finally
        {
            Marshal.FreeHGlobal(puntero);
        }
    }

    private static void CerrarTrabajo()
    {
        if (trabajo != IntPtr.Zero)
        {
            CloseHandle(trabajo);
            trabajo = IntPtr.Zero;
        }
    }

    // --- Comprobaciones -----------------------------------------------------------

    /// Vite puede escuchar solo en IPv6 (::1) y uvicorn solo en IPv4: se prueban los dos.
    private static bool PuertoAbierto(int puerto)
    {
        return Conecta(IPAddress.Loopback, puerto) || Conecta(IPAddress.IPv6Loopback, puerto);
    }

    private static bool Conecta(IPAddress direccion, int puerto)
    {
        try
        {
            using (var cliente = new TcpClient(direccion.AddressFamily))
            {
                IAsyncResult intento = cliente.BeginConnect(direccion, puerto, null, null);
                bool a_tiempo = intento.AsyncWaitHandle.WaitOne(400);
                if (!a_tiempo) return false;
                cliente.EndConnect(intento);
                return true;
            }
        }
        catch (Exception)
        {
            return false;
        }
    }

    private static string PedirSalud()
    {
        try
        {
            var peticion = (HttpWebRequest)WebRequest.Create(Salud);
            peticion.Timeout = 3000;
            using (var respuesta = (HttpWebResponse)peticion.GetResponse())
            using (var lector = new StreamReader(respuesta.GetResponseStream()))
            {
                return lector.ReadToEnd().Replace(" ", "");
            }
        }
        catch (Exception)
        {
            return null;
        }
    }

    // --- Consola ----------------------------------------------------------------------

    private static void Titulo()
    {
        Console.WriteLine();
        Console.WriteLine("  PROBADOR VIRTUAL DE TELAS");
        Console.WriteLine("  ─────────────────────────");
        Console.WriteLine();
    }

    private static void Linea(string quien, string que)
    {
        Console.Write("  " + quien.PadRight(10));
        Console.WriteLine(que);
    }

    private static void Aviso(params string[] lineas)
    {
        Console.ForegroundColor = ConsoleColor.Yellow;
        foreach (string l in lineas) Console.WriteLine("  " + l);
        Console.ResetColor();
    }

    private static void Error(params string[] lineas)
    {
        Console.ForegroundColor = ConsoleColor.Red;
        foreach (string l in lineas) Console.WriteLine("  " + l);
        Console.ResetColor();
    }

    private static void MostrarFinal(string log)
    {
        try
        {
            string[] todas = File.ReadAllLines(log, Encoding.Default);
            int desde = Math.Max(0, todas.Length - 15);
            for (int i = desde; i < todas.Length; i++) Console.WriteLine("    " + todas[i]);
        }
        catch (Exception)
        {
            Console.WriteLine("    (no se pudo leer " + log + ")");
        }
    }

    private static int Salir(int codigo)
    {
        CerrarTrabajo();
        Console.WriteLine();
        Console.WriteLine("  Pulsa Enter para cerrar.");
        Console.ReadLine();
        return codigo;
    }

    // --- Windows ----------------------------------------------------------------------

    private const uint CREATE_SUSPENDED = 0x00000004;
    private const uint CREATE_NO_WINDOW = 0x08000000;
    private const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;
    private const int JobObjectExtendedLimitInformation = 9;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct STARTUPINFO
    {
        public int cb;
        public string lpReserved;
        public string lpDesktop;
        public string lpTitle;
        public int dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
        public short wShowWindow, cbReserved2;
        public IntPtr lpReserved2, hStdInput, hStdOutput, hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct PROCESS_INFORMATION
    {
        public IntPtr hProcess, hThread;
        public int dwProcessId, dwThreadId;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct IO_COUNTERS
    {
        public ulong ReadOperationCount, WriteOperationCount, OtherOperationCount;
        public ulong ReadTransferCount, WriteTransferCount, OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit, JobMemoryLimit, PeakProcessMemoryUsed, PeakJobMemoryUsed;
    }

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern bool CreateProcess(string lpApplicationName, StringBuilder lpCommandLine,
        IntPtr lpProcessAttributes, IntPtr lpThreadAttributes, bool bInheritHandles, uint dwCreationFlags,
        IntPtr lpEnvironment, string lpCurrentDirectory, ref STARTUPINFO lpStartupInfo,
        out PROCESS_INFORMATION lpProcessInformation);

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    private static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string lpName);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool SetInformationJobObject(IntPtr hJob, int infoClass, IntPtr lpInfo, uint cbInfoLength);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern uint ResumeThread(IntPtr hThread);

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern bool CloseHandle(IntPtr hObject);
}
