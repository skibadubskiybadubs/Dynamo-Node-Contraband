using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Dynamo.Graph.Workspaces;
using Dynamo.Wpf.Extensions;

namespace Contrabanda;

/// <summary>
/// Dynamo view extension that adds the "Contrabanda" section to Dynamo's menu bar
/// and exposes a WPF panel for graph inspection and (future) Claude Code integration.
/// </summary>
public class ContrabandaViewExtension : IViewExtension
{
    public string UniqueId => "C0NTRABAN-DA00-0000-0000-000000000001";
    public string Name => "Contrabanda";

    private ViewLoadedParams? _loadedParams;
    private ContrabandaWindow? _window;
    private MenuItem? _topLevelMenu;

    public void Startup(ViewStartupParams p) { }

    public void Loaded(ViewLoadedParams p)
    {
        _loadedParams = p;

        // Inject a top-level "Contrabanda" menu into Dynamo's menu bar
        p.DynamoWindow.Dispatcher.Invoke(() =>
        {
            var menu = FindVisualChild<Menu>(p.DynamoWindow);
            if (menu != null)
            {
                _topLevelMenu = BuildTopLevelMenu();
                menu.Items.Add(_topLevelMenu);
            }
            else
            {
                // Fallback: add under View menu via official API
                var fallbackItem = new MenuItem { Header = "Open Contrabanda" };
                fallbackItem.Click += (_, _) => ShowWindow();
                p.AddMenuItem(MenuBarType.View, fallbackItem);
            }
        });

        p.CurrentWorkspaceChanged += OnCurrentWorkspaceChanged;
    }

    public void Shutdown()
    {
        if (_loadedParams != null)
            _loadedParams.CurrentWorkspaceChanged -= OnCurrentWorkspaceChanged;

        _loadedParams?.DynamoWindow.Dispatcher.Invoke(() =>
        {
            if (_topLevelMenu != null)
            {
                var menu = FindVisualChild<Menu>(_loadedParams.DynamoWindow);
                menu?.Items.Remove(_topLevelMenu);
            }
            _window?.Close();
        });
    }

    public void Dispose() => Shutdown();

    // -------------------------------------------------------------------------

    private MenuItem BuildTopLevelMenu()
    {
        var root = new MenuItem { Header = "Contrabanda" };

        var openItem = new MenuItem { Header = "Open Contrabanda" };
        openItem.Click += (_, _) => ShowWindow();
        root.Items.Add(openItem);

        return root;
    }

    private void ShowWindow()
    {
        if (_loadedParams == null) return;

        _loadedParams.DynamoWindow.Dispatcher.Invoke(() =>
        {
            if (_window == null || !_window.IsLoaded)
            {
                _window = new ContrabandaWindow(_loadedParams);
                _window.Owner = _loadedParams.DynamoWindow;
                _window.Show();
            }
            else
            {
                _window.Activate();
                if (_window.WindowState == WindowState.Minimized)
                    _window.WindowState = WindowState.Normal;
            }
        });
    }

    private void OnCurrentWorkspaceChanged(IWorkspaceModel workspace)
    {
        _loadedParams?.DynamoWindow.Dispatcher.Invoke(() =>
            _window?.UpdateWorkspace(workspace));
    }

    // -------------------------------------------------------------------------

    private static T? FindVisualChild<T>(DependencyObject parent) where T : DependencyObject
    {
        for (int i = 0; i < VisualTreeHelper.GetChildrenCount(parent); i++)
        {
            var child = VisualTreeHelper.GetChild(parent, i);
            if (child is T result)
                return result;
            var found = FindVisualChild<T>(child);
            if (found != null) return found;
        }
        return null;
    }
}
