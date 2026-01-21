'use client';

import {
  Box,
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

export interface CheckboxStructure {
  title: string;
  type: 'label' | 'checkbox';
  checked: boolean;
  seeChildren?: boolean;
  children?: CheckboxStructure[];
  disabled?: boolean;
  props?: Record<string, string>;
}

function useDebouncedCallback(callback: () => void, delay: number): () => void {
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  const debouncedFunction = useCallback(() => {
    if (timeoutRef.current != null) {
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
  if ((checkboxData.disabled != null && checkboxData.disabled) || disableAll) {
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
}: NestedCheckboxListProps): React.ReactElement {
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

  const debouncedSubmit = useDebouncedCallback(() => {
    onCheckboxChange(checkboxStructure);
  }, debounceTime);

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
                        setCheckboxStructure((prev) => {
                          const newData = {
                            ...checkboxData,
                            seeChildren:
                              checkboxData.seeChildren === undefined
                                ? true
                                : !checkboxData.seeChildren,
                          };
                          const newStructure = [...prev];
                          newStructure[index] = newData;
                          if (onExpandGroupChange !== undefined) {
                            onExpandGroupChange(newStructure);
                          }
                          return newStructure;
                        });
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
                    const newCheckedValue = !checkboxData.checked;
                    const newData = {
                      ...checkboxData,
                      checked: newCheckedValue,
                      children: checkboxData.children?.map((child) => ({
                        ...child,
                        checked: newCheckedValue,
                      })),
                    };
                    const newStructure = [...prev];
                    newStructure[index] = newData;
                    return newStructure;
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
                in={
                  checkboxData.seeChildren != null &&
                  checkboxData.seeChildren &&
                  !disableAll
                }
                timeout='auto'
                unmountOnExit
              >
                <Box sx={{ pl: 1, width: '100%' }}>
                  <NestedCheckboxList
                    checkboxData={checkboxData.children}
                    onCheckboxChange={(children) => {
                      setCheckboxStructure((prev) => {
                        const newData = {
                          ...checkboxData,
                          children,
                        };
                        const newStructure = [...prev];
                        newStructure[index] = newData;
                        return newStructure;
                      });
                      setHasChange(true);
                    }}
                    onExpandGroupChange={onExpandGroupChange}
                    disableAll={disableAll || checkboxData.disabled}
                    debounceTime={0}
                  ></NestedCheckboxList>
                </Box>
              </Collapse>
            )}
          </ListItem>
        );
      })}
    </List>
  );
}
