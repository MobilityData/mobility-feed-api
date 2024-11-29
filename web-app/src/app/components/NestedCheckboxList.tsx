import {
  Checkbox,
  Collapse,
  IconButton,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
} from '@mui/material';
import * as React from 'react';
import { ExpandLess, ExpandMore } from '@mui/icons-material';
import { theme } from '../Theme';

interface NestedCheckboxListProps {
  checkboxData: CheckboxStructure[];
  onCheckboxChange: (checkboxData: CheckboxStructure[]) => void;
}

// NOTE: Although the data structure allows for multiple levels of nesting, the current implementation only supports two levels.
// TODO: Implement support for multiple levels of nesting
export interface CheckboxStructure {
  title: string;
  type: 'label' | 'checkbox';
  checked: boolean;
  seeChildren?: boolean;
  children?: CheckboxStructure[];
}

export default function NestedCheckboxList({
  checkboxData,
  onCheckboxChange,
}: NestedCheckboxListProps): JSX.Element {
  const [checkboxStructure, setCheckboxStructure] =
    React.useState<CheckboxStructure[]>(checkboxData);
  const [hasChange, setHasChange] = React.useState<boolean>(false);

  React.useEffect(() => {
    if (hasChange) {
      setHasChange(false);
      onCheckboxChange(checkboxStructure);
    }
  }, [checkboxStructure]);

  React.useEffect(() => {
    setCheckboxStructure(checkboxData);
  }, [checkboxData]);

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
                      edge={'end'}
                      aria-label='expand'
                      onClick={() => {
                        setCheckboxStructure((prev) => {
                          checkboxData.seeChildren =
                            checkboxData.seeChildren === undefined
                              ? true
                              : !checkboxData.seeChildren;
                          return [...prev];
                        });
                        // NOTE: Expand changes will not output to parent
                      }}
                    >
                      {checkboxData.seeChildren !== undefined &&
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
                  checked={
                    checkboxData.checked ||
                    (checkboxData.children !== undefined &&
                      checkboxData.children.length > 0 &&
                      checkboxData.children.every((child) => child.checked))
                  }
                  indeterminate={
                    checkboxData.children !== undefined
                      ? checkboxData.children.some((child) => child.checked) &&
                        !checkboxData.children.every((child) => child.checked)
                      : false
                  }
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
                in={checkboxData.seeChildren}
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
                          dense={true}
                          sx={{ p: 0, pl: 1 }}
                        >
                          <Checkbox
                            edge='start'
                            tabIndex={-1}
                            disableRipple
                            checked={value.checked || checkboxData.checked}
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
