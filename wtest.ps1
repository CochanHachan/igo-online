# wtest.ps1 - Native Windows WebAuthn make_credential probe (zero dependency)
# Run INSIDE the disposable, Hello-UNSET VM, in a normal Windows PowerShell console.
# It calls the SAME OS API that 碁華 would use. It does NOT change Windows sign-in.
# For each test: watch the Windows dialog, screenshot it, then press Esc to cancel.

$ErrorActionPreference = 'Stop'

$cs = @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class WAT
{
    [DllImport("webauthn.dll")]
    public static extern int WebAuthNGetApiVersionNumber();
    [DllImport("webauthn.dll")]
    public static extern int WebAuthNIsUserVerifyingPlatformAuthenticatorAvailable(out bool avail);
    [DllImport("webauthn.dll")]
    public static extern IntPtr WebAuthNGetErrorName(int hr);
    [DllImport("webauthn.dll")]
    public static extern void WebAuthNFreeCredentialAttestation(IntPtr p);
    [DllImport("kernel32.dll")]
    public static extern IntPtr GetConsoleWindow();
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    struct RP { public int v; public string id; public string name; public string icon; }
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    struct USER { public int v; public int cbId; public IntPtr pbId; public string name; public string icon; public string disp; }
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    struct COSE { public int v; public string type; public int alg; }
    [StructLayout(LayoutKind.Sequential)]
    struct COSES { public int c; public IntPtr p; }
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    struct CDATA { public int v; public int cb; public IntPtr pb; public string hash; }
    [StructLayout(LayoutKind.Sequential)]
    struct CREDS { public int c; public IntPtr p; }
    [StructLayout(LayoutKind.Sequential)]
    struct EXTS { public int c; public IntPtr p; }
    [StructLayout(LayoutKind.Sequential)]
    struct MCOPT {
        public int v; public int timeout;
        public CREDS creds; public EXTS exts;
        public int attach; public int rrk; public int uv; public int att; public int flags;
    }

    [DllImport("webauthn.dll")]
    static extern int WebAuthNAuthenticatorMakeCredential(
        IntPtr hWnd, [In] ref RP rp, [In] ref USER user, [In] ref COSES cose,
        [In] ref CDATA cd, [In] ref MCOPT opt, out IntPtr pAtt);

    public static string ApiInfo() {
        int ver = 0; bool uvpaa = false;
        try { ver = WebAuthNGetApiVersionNumber(); } catch {}
        try { WebAuthNIsUserVerifyingPlatformAuthenticatorAvailable(out uvpaa); } catch {}
        return "API version = " + ver + "   |   isUVPAA (Hello usable) = " + uvpaa;
    }

    public static string Make(int attach, int uv, int rrk) {
        RP rp = new RP(); rp.v=1; rp.id="localhost"; rp.name="Goka Test"; rp.icon=null;
        byte[] uid = new byte[]{1,2,3,4,5,6,7,8};
        IntPtr pUid = Marshal.AllocHGlobal(uid.Length); Marshal.Copy(uid,0,pUid,uid.Length);
        USER user = new USER(); user.v=1; user.cbId=uid.Length; user.pbId=pUid;
        user.name="test"; user.icon=null; user.disp="Test User";
        COSE cose1 = new COSE(); cose1.v=1; cose1.type="public-key"; cose1.alg=-7;
        IntPtr pCose = Marshal.AllocHGlobal(Marshal.SizeOf(typeof(COSE)));
        Marshal.StructureToPtr(cose1, pCose, false);
        COSES cose = new COSES(); cose.c=1; cose.p=pCose;
        byte[] cd = Encoding.UTF8.GetBytes("{\"type\":\"webauthn.create\",\"challenge\":\"MTIzNDU2Nzg5MA\",\"origin\":\"https://localhost\"}");
        IntPtr pCd = Marshal.AllocHGlobal(cd.Length); Marshal.Copy(cd,0,pCd,cd.Length);
        CDATA cdata = new CDATA(); cdata.v=1; cdata.cb=cd.Length; cdata.pb=pCd; cdata.hash="SHA-256";
        MCOPT opt = new MCOPT();
        opt.v=1; opt.timeout=120000;
        opt.creds = new CREDS(); opt.creds.c=0; opt.creds.p=IntPtr.Zero;
        opt.exts  = new EXTS();  opt.exts.c=0;  opt.exts.p=IntPtr.Zero;
        opt.attach=attach; opt.rrk=rrk; opt.uv=uv; opt.att=0; opt.flags=0;
        IntPtr hwnd = GetConsoleWindow(); if (hwnd==IntPtr.Zero) hwnd = GetForegroundWindow();
        IntPtr pAtt = IntPtr.Zero;
        int hr = WebAuthNAuthenticatorMakeCredential(hwnd, ref rp, ref user, ref cose, ref cdata, ref opt, out pAtt);
        string nm = "";
        try { IntPtr pn = WebAuthNGetErrorName(hr); if (pn!=IntPtr.Zero) nm = Marshal.PtrToStringUni(pn); } catch {}
        if (pAtt!=IntPtr.Zero) { try { WebAuthNFreeCredentialAttestation(pAtt); } catch {} }
        try { Marshal.DestroyStructure(pCose, typeof(COSE)); } catch {}
        Marshal.FreeHGlobal(pCose); Marshal.FreeHGlobal(pUid); Marshal.FreeHGlobal(pCd);
        return string.Format("HRESULT = 0x{0:X8}   WebAuthNGetErrorName = {1}", (uint)hr, nm);
    }
}
'@

if (-not ('WAT' -as [type])) { Add-Type -TypeDefinition $cs -Language CSharp }

Write-Host ""
Write-Host "============== Native WebAuthn probe ==============" -ForegroundColor Cyan
Write-Host ("Computer : " + $env:COMPUTERNAME)
Write-Host ([WAT]::ApiInfo())
Write-Host ""
Write-Host "This PC's Windows Hello is intentionally NOT set up." -ForegroundColor Yellow
Write-Host "For each test: WATCH the Windows dialog, take a screenshot," -ForegroundColor Yellow
Write-Host "then press Esc / close it to get the result line." -ForegroundColor Yellow
Write-Host ""

Write-Host "----- TEST A : attachment=PLATFORM, UV=REQUIRED, residentKey=REQUIRED -----" -ForegroundColor Green
Write-Host "(this is exactly the P1 / Nov-7 combination)"
[void](Read-Host "Press Enter to start TEST A")
$a = [WAT]::Make(1,1,1)
Write-Host ("TEST A result : " + $a) -ForegroundColor White
Write-Host ""

Write-Host "----- TEST B : attachment=ANY, UV=REQUIRED, residentKey=off -----" -ForegroundColor Green
Write-Host "(the proposed safe recipe: should offer phone / security key instead of forcing Hello)"
[void](Read-Host "Press Enter to start TEST B")
$b = [WAT]::Make(0,1,0)
Write-Host ("TEST B result : " + $b) -ForegroundColor White
Write-Host ""
Write-Host "============== Done ==============" -ForegroundColor Cyan
Write-Host "For EACH test, note which happened:"
Write-Host "  (1) Windows tried to make you SET UP a PIN / Windows Hello  (= guides to setup)"
Write-Host "  (2) a chooser appeared (another device / security key / phone)"
Write-Host "  (3) it failed instantly with an error, no dialog"
Write-Host "Report the two HRESULT lines + what each dialog showed."
