var dagcomponentfuncs = (window.dashAgGridComponentFunctions = window.dashAgGridComponentFunctions || {});

// Header for result grid configuration columns: shows the configuration icon only.
dagcomponentfuncs.ResultConfigHeader = function (props) {
    return React.createElement('i', {className: props.iconClassName});
};
