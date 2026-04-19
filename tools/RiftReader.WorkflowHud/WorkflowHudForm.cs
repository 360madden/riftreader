using System.Drawing.Drawing2D;
using System.Text.Json;
using Timer = System.Windows.Forms.Timer;

namespace RiftReader.WorkflowHud;

internal sealed class WorkflowHudForm : Form
{
    private const int FormWidth = 272;
    private const int FormHeight = 84;
    private const int CornerRadius = 14;
    private const int ScreenMargin = 16;
    private const int ActivePulseIntervalMilliseconds = 160;
    private const int StatusPollIntervalMilliseconds = 400;
    private const int MinimumDisplayDurationMilliseconds = 650;
    private const int DefaultStaleAfterSeconds = 8;

    private readonly WorkflowHudOptions _options;
    private readonly string _utilityVersionLabel;
    private readonly Font _titleFont = new("Segoe UI", 9f, FontStyle.Bold, GraphicsUnit.Point);
    private readonly Font _actionFont = new("Segoe UI", 11f, FontStyle.Regular, GraphicsUnit.Point);
    private readonly Timer _pulseTimer;
    private readonly Timer _statusTimer;
    private readonly JsonSerializerOptions _jsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        WriteIndented = true
    };

    private WorkflowHudStatusDocument _sourceStatus = WorkflowHudStatusDocument.CreateDefault();
    private WorkflowHudStatusDocument _displayStatus = WorkflowHudStatusDocument.CreateDefault();
    private WorkflowHudStatusDocument? _pendingStatus;
    private DateTime _lastStatusFileWriteUtc = DateTime.MinValue;
    private DateTimeOffset _displayStatusChangedUtc = DateTimeOffset.MinValue;
    private double _pulsePhase;
    private bool _dragging;
    private Point _dragOrigin;
    private Point _formOrigin;

    public WorkflowHudForm(WorkflowHudOptions options, string utilityVersionLabel)
    {
        _options = options;
        _utilityVersionLabel = utilityVersionLabel;

        AutoScaleMode = AutoScaleMode.Dpi;
        ClientSize = new Size(FormWidth, FormHeight);
        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = false;
        StartPosition = FormStartPosition.Manual;
        TopMost = true;
        DoubleBuffered = true;
        BackColor = Color.FromArgb(23, 27, 34);
        Opacity = 0.92d;
        MinimumSize = new Size(FormWidth, FormHeight);
        MaximumSize = new Size(FormWidth, FormHeight);
        Cursor = Cursors.SizeAll;
        Text = utilityVersionLabel;

        ApplyRoundedRegion();
        RestoreLocation();
        RefreshStatus(force: true);

        _pulseTimer = new Timer { Interval = ActivePulseIntervalMilliseconds };
        _pulseTimer.Tick += (_, _) =>
        {
            _pulsePhase += 0.33d;
            Invalidate();
        };
        _pulseTimer.Start();

        _statusTimer = new Timer { Interval = StatusPollIntervalMilliseconds };
        _statusTimer.Tick += (_, _) => RefreshStatus(force: false);
        _statusTimer.Start();
    }

    protected override bool ShowWithoutActivation => true;

    protected override CreateParams CreateParams
    {
        get
        {
            const int wsExToolWindow = 0x00000080;
            const int wsExNoActivate = 0x08000000;

            var cp = base.CreateParams;
            cp.ExStyle |= wsExToolWindow | wsExNoActivate;
            return cp;
        }
    }

    protected override void WndProc(ref Message m)
    {
        const int wmMouseActivate = 0x0021;
        const int maNoActivate = 0x0003;

        if (m.Msg == wmMouseActivate)
        {
            m.Result = (IntPtr)maNoActivate;
            return;
        }

        base.WndProc(ref m);
    }

    protected override void OnResize(EventArgs e)
    {
        base.OnResize(e);
        ApplyRoundedRegion();
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);

        e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
        e.Graphics.TextRenderingHint = System.Drawing.Text.TextRenderingHint.ClearTypeGridFit;

        var bounds = ClientRectangle;
        bounds.Inflate(-1, -1);

        using var backgroundPath = CreateRoundedPath(bounds, CornerRadius);
        using var backgroundBrush = new SolidBrush(Color.FromArgb(234, 23, 27, 34));
        using var borderPen = new Pen(Color.FromArgb(96, 162, 172, 186), 1f);
        e.Graphics.FillPath(backgroundBrush, backgroundPath);
        e.Graphics.DrawPath(borderPen, backgroundPath);

        var titleText = _utilityVersionLabel;
        var actionText = FormatActionText(_displayStatus.Action);
        var dotColor = ResolveDotColor(_displayStatus.State);
        const int dotSize = 12;
        const int interLineGap = 6;
        const int dotGap = 9;

        var titleSize = MeasureText(e.Graphics, titleText, _titleFont);
        var actionSize = MeasureText(e.Graphics, actionText, _actionFont);
        var actionRowHeight = Math.Max(dotSize, actionSize.Height);
        var contentHeight = titleSize.Height + interLineGap + actionRowHeight;
        var contentTop = (ClientSize.Height - contentHeight) / 2f;
        var titleRect = new RectangleF(
            (ClientSize.Width - titleSize.Width) / 2f,
            contentTop,
            titleSize.Width,
            titleSize.Height);

        var actionTop = titleRect.Bottom + interLineGap;
        var actionRowWidth = dotSize + dotGap + actionSize.Width;
        var actionLeft = (ClientSize.Width - actionRowWidth) / 2f;
        var dotRect = new RectangleF(
            actionLeft,
            actionTop + (actionRowHeight - dotSize) / 2f,
            dotSize,
            dotSize);
        var actionRect = new RectangleF(
            dotRect.Right + dotGap,
            actionTop + (actionRowHeight - actionSize.Height) / 2f,
            actionSize.Width,
            actionSize.Height);

        using var titleBrush = new SolidBrush(Color.FromArgb(214, 221, 230));
        using var actionBrush = new SolidBrush(Color.FromArgb(244, 248, 252));
        using var dotBrush = new SolidBrush(dotColor);
        using var dotBorderPen = new Pen(Color.FromArgb(92, 255, 255, 255), 1f);

        e.Graphics.DrawString(titleText, _titleFont, titleBrush, titleRect.Location);
        e.Graphics.FillEllipse(dotBrush, dotRect);
        e.Graphics.DrawEllipse(dotBorderPen, dotRect);
        e.Graphics.DrawString(actionText, _actionFont, actionBrush, actionRect.Location);
    }

    protected override void OnMouseDown(MouseEventArgs e)
    {
        base.OnMouseDown(e);
        if (e.Button != MouseButtons.Left)
        {
            return;
        }

        _dragging = true;
        _dragOrigin = Cursor.Position;
        _formOrigin = Location;
    }

    protected override void OnMouseMove(MouseEventArgs e)
    {
        base.OnMouseMove(e);
        if (!_dragging)
        {
            return;
        }

        var cursorPosition = Cursor.Position;
        var deltaX = cursorPosition.X - _dragOrigin.X;
        var deltaY = cursorPosition.Y - _dragOrigin.Y;
        Location = ClampToWorkingArea(new Point(_formOrigin.X + deltaX, _formOrigin.Y + deltaY));
    }

    protected override void OnMouseUp(MouseEventArgs e)
    {
        base.OnMouseUp(e);
        if (e.Button != MouseButtons.Left)
        {
            return;
        }

        if (_dragging)
        {
            _dragging = false;
            PersistLocation();
        }
    }

    protected override void OnFormClosed(FormClosedEventArgs e)
    {
        PersistLocation();
        _pulseTimer.Stop();
        _statusTimer.Stop();
        _titleFont.Dispose();
        _actionFont.Dispose();
        base.OnFormClosed(e);
    }

    private void RefreshStatus(bool force)
    {
        try
        {
            if (!File.Exists(_options.StatusFilePath))
            {
                if (force)
                {
                    _sourceStatus = WorkflowHudStatusDocument.CreateDefault();
                    ApplyDisplayStatus(_sourceStatus, force: true);
                }

                CommitPendingStatusIfDue();
                return;
            }

            var lastWriteUtc = File.GetLastWriteTimeUtc(_options.StatusFilePath);
            if (force || lastWriteUtc != _lastStatusFileWriteUtc)
            {
                using var stream = File.Open(_options.StatusFilePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                var parsed = JsonSerializer.Deserialize<WorkflowHudStatusDocument>(stream, _jsonOptions) ?? WorkflowHudStatusDocument.CreateDefault();
                _sourceStatus = NormalizeStatusDocument(parsed);
                _lastStatusFileWriteUtc = lastWriteUtc;
            }

            var effectiveStatus = GetEffectiveStatus(_sourceStatus);
            ApplyDisplayStatus(effectiveStatus, force);
        }
        catch
        {
            if (force)
            {
                _sourceStatus = WorkflowHudStatusDocument.CreateBlocked("status file unreadable");
                ApplyDisplayStatus(_sourceStatus, force: true);
            }
        }

        CommitPendingStatusIfDue();
    }

    private void RestoreLocation()
    {
        try
        {
            if (File.Exists(_options.ConfigFilePath))
            {
                using var stream = File.Open(_options.ConfigFilePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                var config = JsonSerializer.Deserialize<WorkflowHudConfigDocument>(stream, _jsonOptions);
                if (config is not null && config.X.HasValue && config.Y.HasValue)
                {
                    Location = ClampToWorkingArea(new Point(config.X.Value, config.Y.Value));
                    return;
                }
            }
        }
        catch
        {
            // Fall back to the default position below.
        }

        var workArea = Screen.PrimaryScreen?.WorkingArea ?? Screen.FromPoint(Cursor.Position).WorkingArea;
        Location = new Point(
            workArea.Right - Width - ScreenMargin,
            workArea.Top + ScreenMargin);
    }

    private void PersistLocation()
    {
        try
        {
            var directory = Path.GetDirectoryName(_options.ConfigFilePath);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }

            var document = new WorkflowHudConfigDocument(Location.X, Location.Y);
            var payload = JsonSerializer.Serialize(document, _jsonOptions);
            var tempFile = $"{_options.ConfigFilePath}.tmp";
            File.WriteAllText(tempFile, payload);
            File.Move(tempFile, _options.ConfigFilePath, overwrite: true);
        }
        catch
        {
            // Position persistence is best-effort only for the prototype.
        }
    }

    private void ApplyRoundedRegion()
    {
        Region?.Dispose();
        using var path = CreateRoundedPath(ClientRectangle, CornerRadius);
        Region = new Region(path);
    }

    private Point ClampToWorkingArea(Point requestedLocation)
    {
        var currentBounds = new Rectangle(requestedLocation, Size);
        var targetScreen = Screen.AllScreens.FirstOrDefault(screen => screen.WorkingArea.IntersectsWith(currentBounds))
            ?? Screen.AllScreens.FirstOrDefault(screen => screen.WorkingArea.Contains(requestedLocation))
            ?? Screen.PrimaryScreen
            ?? Screen.FromPoint(Cursor.Position);

        var workArea = targetScreen.WorkingArea;
        var x = Math.Min(Math.Max(requestedLocation.X, workArea.Left), workArea.Right - Width);
        var y = Math.Min(Math.Max(requestedLocation.Y, workArea.Top), workArea.Bottom - Height);
        return new Point(x, y);
    }

    private static GraphicsPath CreateRoundedPath(Rectangle bounds, int radius)
    {
        var path = new GraphicsPath();
        var diameter = radius * 2;
        var arc = new Rectangle(bounds.X, bounds.Y, diameter, diameter);
        path.AddArc(arc, 180, 90);
        arc.X = bounds.Right - diameter;
        path.AddArc(arc, 270, 90);
        arc.Y = bounds.Bottom - diameter;
        path.AddArc(arc, 0, 90);
        arc.X = bounds.Left;
        path.AddArc(arc, 90, 90);
        path.CloseFigure();
        return path;
    }

    private static SizeF MeasureText(Graphics graphics, string text, Font font)
    {
        var size = graphics.MeasureString(text, font, int.MaxValue, StringFormat.GenericTypographic);
        return new SizeF((float)Math.Ceiling(size.Width), (float)Math.Ceiling(size.Height));
    }

    private static string NormalizeState(string? state)
    {
        return state?.Trim().ToLowerInvariant() switch
        {
            "active" => "active",
            "waiting" => "waiting",
            "blocked" => "blocked",
            _ => "idle"
        };
    }

    private static string FormatActionText(string? action)
    {
        const int maxLength = 28;
        var normalized = string.IsNullOrWhiteSpace(action) ? "idle" : action.Trim();
        if (normalized.Length <= maxLength)
        {
            return normalized;
        }

        return $"{normalized[..(maxLength - 1)].TrimEnd()}…";
    }

    private WorkflowHudStatusDocument NormalizeStatusDocument(WorkflowHudStatusDocument parsed)
    {
        var normalizedState = NormalizeState(parsed.State);
        var normalizedAction = string.IsNullOrWhiteSpace(parsed.Action)
            ? (string.IsNullOrWhiteSpace(parsed.LastMessage) ? (normalizedState == "idle" ? "idle" : "working") : parsed.LastMessage.Trim())
            : parsed.Action.Trim();
        var normalizedLastMessage = string.IsNullOrWhiteSpace(parsed.LastMessage)
            ? (normalizedAction.Equals("idle", StringComparison.OrdinalIgnoreCase) ? null : normalizedAction)
            : parsed.LastMessage.Trim();
        var staleAfterSeconds = parsed.StaleAfterSeconds is > 0 ? parsed.StaleAfterSeconds.Value : DefaultStaleAfterSeconds;

        return parsed with
        {
            State = normalizedState,
            Action = normalizedAction,
            LastMessage = normalizedLastMessage,
            StaleAfterSeconds = staleAfterSeconds
        };
    }

    private WorkflowHudStatusDocument GetEffectiveStatus(WorkflowHudStatusDocument source)
    {
        var normalized = NormalizeStatusDocument(source);
        if (normalized.UpdatedAtUtc.HasValue &&
            NormalizeState(normalized.State) is "active" or "waiting" &&
            normalized.StaleAfterSeconds.GetValueOrDefault(DefaultStaleAfterSeconds) > 0)
        {
            var age = DateTimeOffset.UtcNow - normalized.UpdatedAtUtc.Value;
            if (age > TimeSpan.FromSeconds(normalized.StaleAfterSeconds!.Value))
            {
                var staleAction = string.IsNullOrWhiteSpace(normalized.LastMessage)
                    ? "status stale"
                    : $"stale: {normalized.LastMessage}";
                return normalized with
                {
                    State = "waiting",
                    Action = staleAction
                };
            }
        }

        return normalized;
    }

    private void ApplyDisplayStatus(WorkflowHudStatusDocument candidate, bool force)
    {
        if (force)
        {
            CommitDisplayStatus(candidate);
            _pendingStatus = null;
            return;
        }

        if (AreEquivalent(_displayStatus, candidate))
        {
            _pendingStatus = null;
            return;
        }

        var elapsed = DateTimeOffset.UtcNow - _displayStatusChangedUtc;
        if (elapsed < TimeSpan.FromMilliseconds(MinimumDisplayDurationMilliseconds) &&
            !ShouldBypassDebounce(_displayStatus, candidate))
        {
            _pendingStatus = candidate;
            return;
        }

        CommitDisplayStatus(candidate);
        _pendingStatus = null;
    }

    private void CommitPendingStatusIfDue()
    {
        if (_pendingStatus is null)
        {
            return;
        }

        var elapsed = DateTimeOffset.UtcNow - _displayStatusChangedUtc;
        if (elapsed < TimeSpan.FromMilliseconds(MinimumDisplayDurationMilliseconds))
        {
            return;
        }

        CommitDisplayStatus(_pendingStatus);
        _pendingStatus = null;
    }

    private void CommitDisplayStatus(WorkflowHudStatusDocument status)
    {
        _displayStatus = status;
        _displayStatusChangedUtc = DateTimeOffset.UtcNow;
        Invalidate();
    }

    private static bool ShouldBypassDebounce(WorkflowHudStatusDocument current, WorkflowHudStatusDocument next)
    {
        var currentState = NormalizeState(current.State);
        var nextState = NormalizeState(next.State);
        return currentState == "idle" || nextState == "blocked";
    }

    private static bool AreEquivalent(WorkflowHudStatusDocument left, WorkflowHudStatusDocument right)
    {
        return string.Equals(NormalizeState(left.State), NormalizeState(right.State), StringComparison.Ordinal) &&
               string.Equals(left.Action?.Trim(), right.Action?.Trim(), StringComparison.Ordinal) &&
               string.Equals(left.LastMessage?.Trim(), right.LastMessage?.Trim(), StringComparison.Ordinal);
    }

    private Color ResolveDotColor(string? state)
    {
        return NormalizeState(state) switch
        {
            "active" => PulseGreen(),
            "waiting" => Color.FromArgb(244, 196, 82),
            "blocked" => Color.FromArgb(237, 88, 88),
            _ => Color.FromArgb(122, 132, 145)
        };
    }

    private Color PulseGreen()
    {
        var pulse = (Math.Sin(_pulsePhase) + 1d) / 2d;
        var alphaScale = 0.60d + (pulse * 0.40d);
        var red = (int)Math.Round(56d * alphaScale);
        var green = (int)Math.Round(226d * alphaScale);
        var blue = (int)Math.Round(108d * alphaScale);
        return Color.FromArgb(255, red, green, blue);
    }
}

internal sealed record WorkflowHudOptions(string StatusFilePath, string ConfigFilePath)
{
    public static WorkflowHudOptions Parse(string[] args)
    {
        var repoRoot = ResolveRepositoryRoot();
        var statusFilePath = Path.Combine(repoRoot, "debug", "workflow-hud-status.json");
        var configFilePath = Path.Combine(repoRoot, "debug", "workflow-hud-config.json");

        for (var index = 0; index < args.Length; index++)
        {
            var argument = args[index];
            if (string.Equals(argument, "--status-file", StringComparison.OrdinalIgnoreCase) && index + 1 < args.Length)
            {
                statusFilePath = Path.GetFullPath(args[++index]);
            }
            else if (string.Equals(argument, "--config-file", StringComparison.OrdinalIgnoreCase) && index + 1 < args.Length)
            {
                configFilePath = Path.GetFullPath(args[++index]);
            }
        }

        return new WorkflowHudOptions(statusFilePath, configFilePath);
    }

    private static string ResolveRepositoryRoot()
    {
        var current = new DirectoryInfo(AppContext.BaseDirectory);
        while (current is not null)
        {
            var solutionPath = Path.Combine(current.FullName, "RiftReader.slnx");
            if (File.Exists(solutionPath))
            {
                return current.FullName;
            }

            current = current.Parent;
        }

        return Directory.GetCurrentDirectory();
    }
}

internal sealed record WorkflowHudStatusDocument(
    string? State,
    string? Action,
    DateTimeOffset? UpdatedAtUtc = null,
    string? LastMessage = null,
    DateTimeOffset? LastMessageAtUtc = null,
    int? StaleAfterSeconds = null)
{
    private const int DefaultDocumentStaleAfterSeconds = 8;

    public static WorkflowHudStatusDocument CreateDefault() =>
        new("idle", "waiting for status", null, "waiting for status", null, DefaultDocumentStaleAfterSeconds);

    public static WorkflowHudStatusDocument CreateBlocked(string action) =>
        new("blocked", action, DateTimeOffset.UtcNow, action, DateTimeOffset.UtcNow, DefaultDocumentStaleAfterSeconds);
}

internal sealed record WorkflowHudConfigDocument(int? X, int? Y);
