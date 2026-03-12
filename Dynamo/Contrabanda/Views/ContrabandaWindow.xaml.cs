using System.ComponentModel;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using Dynamo.Graph.Nodes;
using Dynamo.Graph.Workspaces;
using Dynamo.Wpf.Extensions;

namespace Contrabanda;

/// <summary>
/// WPF panel for the Contrabanda extension.
/// Displays the active Dynamo graph, the open Revit project, a mock chat window
/// for future Claude Code integration, and a footer showing selected node IDs.
/// </summary>
public partial class ContrabandaWindow : Window
{
    private readonly ViewLoadedParams _params;
    private IWorkspaceModel? _currentWorkspace;

    // Track which nodes we have subscribed to, to avoid double-subscription
    // and to allow clean unsubscribe.
    private readonly HashSet<NodeModel> _subscribedNodes = new();

    public ContrabandaWindow(ViewLoadedParams p)
    {
        InitializeComponent();
        _params = p;

        // Seed the initial workspace (may be null at first startup)
        UpdateWorkspace(p.CurrentWorkspaceModel);

        // Revit project does not change while the window is open (project switch
        // would close/reopen Dynamo), so we read it once here.
        TbRevitProject.Text = GetRevitProjectName();
    }

    // =========================================================================
    // Public API called by the view extension
    // =========================================================================

    /// <summary>
    /// Switch to a different workspace (called when the user opens a new graph).
    /// </summary>
    public void UpdateWorkspace(IWorkspaceModel? workspace)
    {
        UnsubscribeWorkspace(_currentWorkspace);
        _currentWorkspace = workspace;
        SubscribeWorkspace(workspace);

        Dispatcher.Invoke(() =>
        {
            TbGraphName.Text = workspace?.Name is { Length: > 0 } name ? name : "(no graph open)";
            UpdateSelectionFooter();
        });
    }

    // =========================================================================
    // Workspace event wiring
    // =========================================================================

    private void SubscribeWorkspace(IWorkspaceModel? ws)
    {
        if (ws == null) return;
        ws.NodeAdded   += OnNodeAdded;
        ws.NodeRemoved += OnNodeRemoved;

        // Subscribe to all nodes already in the workspace
        foreach (var node in ws.Nodes)
            SubscribeNode(node);
    }

    private void UnsubscribeWorkspace(IWorkspaceModel? ws)
    {
        if (ws == null) return;
        ws.NodeAdded   -= OnNodeAdded;
        ws.NodeRemoved -= OnNodeRemoved;

        // Unsubscribe from every node we were tracking
        foreach (var node in _subscribedNodes.ToList())
            UnsubscribeNode(node);
    }

    private void SubscribeNode(NodeModel node)
    {
        if (_subscribedNodes.Add(node))
            node.PropertyChanged += OnNodePropertyChanged;
    }

    private void UnsubscribeNode(NodeModel node)
    {
        if (_subscribedNodes.Remove(node))
            node.PropertyChanged -= OnNodePropertyChanged;
    }

    // =========================================================================
    // Event handlers
    // =========================================================================

    private void OnNodeAdded(NodeModel node) => SubscribeNode(node);

    private void OnNodeRemoved(NodeModel node)
    {
        UnsubscribeNode(node);
        UpdateSelectionFooter();
    }

    private void OnNodePropertyChanged(object? sender, PropertyChangedEventArgs e)
    {
        if (e.PropertyName == nameof(NodeModel.IsSelected))
            UpdateSelectionFooter();
    }

    // =========================================================================
    // Footer update
    // =========================================================================

    private void UpdateSelectionFooter()
    {
        Dispatcher.Invoke(() =>
        {
            if (_currentWorkspace == null)
            {
                TbSelectedNodes.Text = "(none)";
                return;
            }

            var selected = _currentWorkspace.Nodes
                .Where(n => n.IsSelected)
                .Select(n => n.GUID.ToString())
                .ToList();

            TbSelectedNodes.Text = selected.Count > 0
                ? string.Join(",  ", selected)
                : "(none)";
        });
    }

    // =========================================================================
    // Chat (mock)
    // =========================================================================

    private void BtnSend_Click(object sender, RoutedEventArgs e) => SendMessage();

    private void TbInput_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter && !Keyboard.IsKeyDown(Key.LeftShift)
                               && !Keyboard.IsKeyDown(Key.RightShift))
        {
            e.Handled = true;
            SendMessage();
        }
    }

    private void SendMessage()
    {
        var text = TbInput.Text.Trim();
        if (string.IsNullOrEmpty(text)) return;

        TbInput.Clear();

        AppendChatBubble(text, isUser: true);

        // Mock Claude response
        AppendChatBubble(
            "Claude Code integration coming soon. Your message was received: \"" + text + "\"",
            isUser: false);

        ChatScroll.ScrollToBottom();
    }

    private void AppendChatBubble(string text, bool isUser)
    {
        var bubble = new Border
        {
            Background   = isUser
                ? new SolidColorBrush(Color.FromRgb(0x0E, 0x70, 0xB0))  // blue user
                : new SolidColorBrush(Color.FromRgb(0x3A, 0x3A, 0x3C)), // dark bot
            CornerRadius = isUser ? new CornerRadius(12, 12, 2, 12) : new CornerRadius(12, 12, 12, 2),
            Padding      = new Thickness(12, 8, 12, 8),
            Margin       = isUser
                ? new Thickness(80, 4, 0, 4)
                : new Thickness(0, 4, 80, 4),
            HorizontalAlignment = isUser ? HorizontalAlignment.Right : HorizontalAlignment.Left,
            MaxWidth     = 620,
        };

        bubble.Child = new TextBlock
        {
            Text             = text,
            Foreground       = Brushes.White,
            TextWrapping     = TextWrapping.Wrap,
            FontSize         = 13,
        };

        ChatMessages.Children.Add(bubble);
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private static string GetRevitProjectName()
    {
        try
        {
            // RevitServices is only available when running inside Revit.
            // Wrap in try/catch so the window still works in Dynamo Sandbox.
            var doc = RevitServices.Persistence.DocumentManager.Instance.CurrentDBDocument;
            return doc?.Title is { Length: > 0 } title ? title : "(no Revit project)";
        }
        catch
        {
            return "(no Revit project)";
        }
    }

    // =========================================================================
    // Cleanup on close
    // =========================================================================

    protected override void OnClosed(EventArgs e)
    {
        base.OnClosed(e);
        UnsubscribeWorkspace(_currentWorkspace);
    }
}
