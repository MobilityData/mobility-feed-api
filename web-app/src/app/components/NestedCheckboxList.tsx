import {
  Checkbox,
  Collapse,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  useTheme,
} from '@mui/material';
import * as React from 'react';
import { ExpandLess, ExpandMore } from '@mui/icons-material';
import { useCallback, useRef } from 'react';

interface NestedCheckboxListProps {
  checkboxData: CheckboxStructure[];
  onCheckboxChange: (checkboxData: CheckboxStructure[]) => void;
  onExpandGroupChange?: (checkboxData: CheckboxStructure[]) => void;
  disableAll?: boolean;
  debounceTime?: number;
}

// NOTE: Although the data structure allows for multiple levels of nesting, the current implementation only supports two levels.
// TODO: Implement support for multiple levels of nesting
export interface CheckboxStructure {
  title: string;
  type: 'label' | 'checkbox';
  checked: boolean;
  seeChildren?: boolean;
  children?: CheckboxStructure[];
  disabled?: boolean;
}

function useDebouncedCallback(callback: () => void, delay: number) {
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const debouncedFunction = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(() => {
      callback();
    }, delay);
  }, [callback, delay]);

  return debouncedFunction;
}

export const checkboxCheckValue = (
  checkboxData: CheckboxStructure,
  disableAll: boolean,
): boolean => {
  if (checkboxData.disabled || disableAll) {
    return false;
  }
  return (
    checkboxData.checked ||
    (checkboxData.children !== undefined &&
      checkboxData.children.length > 0 &&
      checkboxData.children.every((child) => child.checked))
  );
};

export const checkboxIndeterminateValue = (
  checkboxData: CheckboxStructure,
  disableAll: boolean,
): boolean => {
  if (disableAll || checkboxData.children == undefined) {
    return false;
  }
  const checkboxCheck =
    checkboxData.children.some((child) => child.checked) &&
    !checkboxData.children.every((child) => child.checked);
  const areAllChildrenDisabled = checkboxData.children.every(
    (child) => child.disabled,
  );
  return !areAllChildrenDisabled && checkboxCheck;
};

export default function NestedCheckboxList({
  checkboxData,
  onCheckboxChange,
  onExpandGroupChange,
  disableAll = false,
  debounceTime = 0,
}: NestedCheckboxListProps): JSX.Element {
  const [checkboxStructure, setCheckboxStructure] = React.useState<
    CheckboxStructure[]
  >([...checkboxData]);
  const [hasChange, setHasChange] = React.useState<boolean>(false);
  const theme = useTheme();

  React.useEffect(() => {
    if (hasChange) {
      setHasChange(false);
      debouncedSubmit();
    }
  }, [checkboxStructure]);

  React.useEffect(() => {
    setCheckboxStructure(checkboxData);
  }, [checkboxData]);

  const debouncedSubmit = useDebouncedCallback(
    () => onCheckboxChange(checkboxStructure),
    debounceTime,
  );

  return (
    <List sx={{ width: '100%' }} dense>
      {checkboxStructure.map((checkboxData, index) => {
        const labelId = `checkbox-list-label-${checkboxData.title}`;
        return (
          <ListItem
            key={checkboxData.title}
            disablePadding
            sx={{
              display: 'block',
              borderBottom:
                checkboxData.children !== undefined
                  ? `1px solid ${theme.palette.text.primary}`
                  : 'none',
              '.MuiListItemSecondaryAction-root': {
                top: checkboxData.type === 'checkbox' ? '22px' : '11px',
              },
            }}
            secondaryAction={
              <>
                {checkboxData.children !== undefined &&
                  checkboxData.children?.length > 0 && (
                    <IconButton
                      disabled={disableAll || checkboxData.disabled}
                      edge={'end'}
                      aria-label='expand'
                      onClick={() => {
                        checkboxData.seeChildren =
                          checkboxData.seeChildren === undefined
                            ? true
                            : !checkboxData.seeChildren;
                        checkboxStructure[index] = checkboxData;
                        setCheckboxStructure([...checkboxStructure]);
                        if (onExpandGroupChange !== undefined) {
                          onExpandGroupChange([...checkboxStructure]);
                        }
                      }}
                    >
                      {!disableAll &&
                      checkboxData.seeChildren != undefined &&
                      checkboxData.seeChildren ? (
                        <ExpandLess />
                      ) : (
                        <ExpandMore />
                      )}
                    </IconButton>
                  )}
              </>
            }
          >
            {checkboxData.type === 'checkbox' && (
              <ListItemButton
                role={undefined}
                disabled={disableAll || checkboxData.disabled}
                dense={true}
                sx={{ p: 0 }}
                onClick={() => {
                  setCheckboxStructure((prev) => {
                    checkboxData.checked = !checkboxData.checked;
                    checkboxData.children?.forEach((child) => {
                      child.checked = checkboxData.checked;
                    });
                    prev[index] = checkboxData;
                    return [...prev];
                  });
                  setHasChange(true);
                }}
              >
                <Checkbox
                  edge='start'
                  tabIndex={-1}
                  disableRipple
                  inputProps={{ 'aria-labelledby': labelId }}
                  checked={checkboxCheckValue(checkboxData, disableAll)}
                  indeterminate={checkboxIndeterminateValue(
                    checkboxData,
                    disableAll,
                  )}
                />
                <ListItemText
                  id={labelId}
                  primary={<b>{checkboxData.title}</b>}
                  primaryTypographyProps={{
                    variant: 'body1',
                  }}
                />
              </ListItemButton>
            )}
            {checkboxData.type === 'label' && (
              <ListItemText
                id={labelId}
                primary={<b>{checkboxData.title}</b>}
                primaryTypographyProps={{
                  variant: 'body1',
                }}
              />
            )}
            {checkboxData.children !== undefined && (
              <Collapse
                in={checkboxData.seeChildren && !disableAll}
                timeout='auto'
                unmountOnExit
              >
                <List
                  sx={{
                    ml: 1,
                    display: { xs: 'flex', md: 'block' },
                    flexWrap: 'wrap',
                  }}
                  dense
                >
                  {checkboxData.children.map((value) => {
                    const labelId = `checkbox-list-label-${value.title}`;

                    return (
                      <ListItem
                        key={value.title}
                        disablePadding
                        sx={{ width: { xs: '50%', sm: '33%', md: '100%' } }}
                        onClick={() => {
                          setCheckboxStructure((prev) => {
                            value.checked = !value.checked;
                            if (!value.checked) {
                              checkboxData.checked = false;
                            }
                            return [...prev];
                          });
                          setHasChange(true);
                        }}
                      >
                        <ListItemButton
                          role={undefined}
                          disabled={disableAll || value.disabled}
                          dense={true}
                          sx={{ p: 0, pl: 1 }}
                        >
                          <Checkbox
                            edge='start'
                            tabIndex={-1}
                            disableRipple
                            checked={
                              !value.disabled &&
                              !disableAll &&
                              (value.checked || checkboxData.checked)
                            }
                            inputProps={{ 'aria-labelledby': labelId }}
                          />

                          <ListItemText
                            id={labelId}
                            primary={`${value.title}`}
                            primaryTypographyProps={{
                              variant: 'body1',
                            }}
                          />
                        </ListItemButton>
                      </ListItem>
                    );
                  })}
                </List>
              </Collapse>
            )}
          </ListItem>
        );
      })}
    </List>
  );
}
