## Alert

**Import:** `import { Alert } from "./ld/Alert"`

- `a11yIconLabel`: string
- `actionButtonProps`: AlertActionButtonProps
- `children`: ReactNode (required)
- `variant`: "error" | "info" | "success" | "warning"

## Badge

**Import:** `import { Badge } from "./ld/Badge"`

- `children`: ReactNode
- `color`: "blue" | "brand" | "brandBold" | "cyan" | "edited" | "gray" | "green" | "info" | "negative" | "neutral" | "orange" | "pink" | "positive" | "purple" | "red" | "spark" | "teal" | "warning" | "yellow"

## Banner

**Import:** `import { Banner } from "./ld/Banner"`

- `closeButtonProps`: BannerCloseButtonProps
- `children`: ReactNode (required)
- `onClose`: (event: MouseEvent<HTMLButtonElement>) => void (required)
- `variant`: "error" | "info" | "success" | "warning"

## BottomSheet

**Import:** `import { BottomSheet } from "./ld/BottomSheet"`

- `actions`: ReactNode
- `closeButtonProps`: BottomSheetCloseButtonProps
- `children`: ReactNode (required)
- `isOpen`: boolean
- `onClose`: (event: BottomSheetCloseEvent) => void (required)
- `onClosed`: () => void
- `title`: ReactNode (required)

## BreadcrumbItem

**Import:** `import { BreadcrumbItem } from "./ld/Breadcrumb"`

- `children`: ReactNode (required)
- `href`: string (required)
- `isCurrent`: boolean
- `onClick`: (event: MouseEvent<HTMLAnchorElement>) => void
- `target`: string

## Breadcrumb

**Import:** `import { Breadcrumb } from "./ld/Breadcrumb"`

- `a11yLabel`: string
- `children`: ReactNode (required)

## ButtonGroup

**Import:** `import { ButtonGroup } from "./ld/Button"`

- `children`: ReactNode (required)

## Button

**Import:** `import { Button } from "./ld/Button"`

- `children`: ReactNode
- `isFullWidth`: boolean
- `isLoading`: boolean
- `leading`: ReactNode
- `size`: "large" | "medium" | "small"
- `trailing`: ReactNode
- `variant`: "destructive" | "primary" | "secondary" | "tertiary"
- `href`: string (required)
- `disabled`: boolean
- `type`: "button" | "reset" | "submit"

## Callout

**Import:** `import { Callout } from "./ld/Callout"`

- `a11yContentLabel`: string (required)
- `children`: ReactNode (required)
- `isOpen`: boolean
- `position`: CalloutPosition
- `trigger`: ReactElement (required)
- `triggerRef`: RefObject<HTMLElement> (required)
- `closeButtonProps`: CalloutCloseButtonProps
- `onClose`: (event: MouseEvent) => void (required)

## CardActions

**Import:** `import { CardActions } from "./ld/Card"`

- `children`: ReactNode (required)

## CardContent

**Import:** `import { CardContent } from "./ld/Card"`

- `children`: ReactNode (required)

## CardHeader

**Import:** `import { CardHeader } from "./ld/Card"`

- `leadingIcon`: ReactNode
- `title`: ReactNode (required)
- `trailing`: ReactNode

## CardMedia

**Import:** `import { CardMedia } from "./ld/Card"`

- `children`: ReactNode (required)

## Card

**Import:** `import { Card } from "./ld/Card"`

- `children`: ReactNode (required)
- `size`: "large" | "small"

## Checkbox

**Import:** `import { Checkbox } from "./ld/Checkbox"`

- `a11yLabelledBy`: string
- `label`: ReactNode
- `checkboxProps`: ComponentPropsWithoutRef<"input">
- `checked`: boolean
- `disabled`: boolean
- `id`: string
- `indeterminate`: boolean
- `name`: string
- `onChange`: (event: ChangeEvent<HTMLInputElement>) => void
- `value`: number | string

## ChipGroup

**Import:** `import { ChipGroup } from "./ld/Chip"`

- `children`: ReactNode (required)

## Chip

**Import:** `import { Chip } from "./ld/Chip"`

- `children`: ReactNode (required)
- `disabled`: boolean
- `leading`: ReactNode
- `onClick`: (event: MouseEvent<HTMLButtonElement>) => void
- `selected`: boolean
- `size`: "large" | "small"
- `trailing`: ReactNode

## Collapse

**Import:** `import { Collapse } from "./ld/Collapse"`

- `isOpen`: boolean

## Container

**Import:** `import { Container } from "./ld/Container"`

- `children`: ReactNode (required)

## DataTableBulkActions

**Import:** `import { DataTableBulkActions } from "./ld/DataTable"`

- `a11yLabel`: string
- `actionContent`: ReactNode
- `count`: number
- `countLabel`: string
- `onClearSelectedButtonProps`: DataTableBulkActionsButtonProps
- `onClearSelected`: (event: MouseEvent<HTMLButtonElement, MouseEvent>) => void
- `onSelectAll`: (event: MouseEvent<HTMLButtonElement, MouseEvent>) => void
- `selectAllButtonProps`: DataTableBulkActionsButtonProps

## DataTableCell

**Import:** `import { DataTableCell } from "./ld/DataTable"`

- `children`: ReactNode (required)
- `variant`: "alphanumeric" | "numeric"

## DataTableCellActions

**Import:** `import { DataTableCellActions } from "./ld/DataTable"`

- `children`: ReactNode (required)

## DataTableCellBulkEditTextArea

**Import:** `import { DataTableCellBulkEditTextArea } from "./ld/DataTable"`

- `a11yTextAreaLabelledBy`: string (required)
- `editedHelperTextLabel`: string
- `error`: ReactNode
- `isEdited`: boolean
- `onChange`: (event: ChangeEvent<HTMLTextAreaElement>) => void (required)
- `textAreaProps`: ComponentPropsWithRef<"textarea">
- `value`: string
- `variant`: "alphanumeric" | "numeric"

## DataTableCellInlineEditTextArea

**Import:** `import { DataTableCellInlineEditTextArea } from "./ld/DataTable"`

- `a11yDialogLabel`: string (required)
- `a11yEditableLabel`: string
- `a11ySavedLabel`: string
- `a11yTextAreaLabel`: string (required)
- `cancelButtonProps`: Omit<LinkButtonButtonProps, "size">
- `error`: ReactNode
- `isOpen`: boolean
- `isSaved`: boolean
- `onCancel`: (event: MouseEvent<HTMLButtonElement, MouseEvent> | KeyboardEvent) => void (required)
- `onChange`: (event: ChangeEvent<HTMLTextAreaElement>) => void (required)
- `onOpen`: (event: MouseEvent<HTMLButtonElement, MouseEvent>) => void (required)
- `onSave`: (event: MouseEvent<HTMLButtonElement, MouseEvent>) => void (required)
- `saveButtonProps`: Omit<ButtonButtonProps, "size" | "variant">
- `textAreaProps`: ComponentPropsWithRef<"textarea">
- `triggerButtonProps`: ComponentPropsWithoutRef<"button">
- `value`: string (required)
- `variant`: "alphanumeric" | "numeric"

## DataTableCellSelect

**Import:** `import { DataTableCellSelect } from "./ld/DataTable"`

- `a11yLabelledBy`: string (required)
- `checkboxProps`: CheckboxA11yProps["checkboxProps"]
- `checked`: CheckboxA11yProps["checked"]
- `disabled`: CheckboxA11yProps["disabled"]
- `name`: CheckboxA11yProps["name"]
- `onChange`: CheckboxA11yProps["onChange"] (required)
- `value`: CheckboxA11yProps["value"]

## DataTableCellStatus

**Import:** `import { DataTableCellStatus } from "./ld/DataTable"`

- `children`: ReactNode (required)

## DataTableHeaderSelect

**Import:** `import { DataTableHeaderSelect } from "./ld/DataTable"`

- `a11yCheckboxLabel`: string
- `checkboxProps`: CheckboxA11yProps["checkboxProps"]
- `checked`: CheckboxA11yProps["checked"]
- `disabled`: CheckboxA11yProps["disabled"]
- `indeterminate`: CheckboxA11yProps["indeterminate"]
- `name`: CheckboxA11yProps["name"]
- `onChange`: CheckboxA11yProps["onChange"] (required)
- `value`: CheckboxA11yProps["value"]

## DateField

**Import:** `import { DateField } from "./ld/DateField"`

- `disabled`: boolean
- `error`: ReactNode
- `format`: string
- `helperText`: ReactNode
- `id`: string
- `label`: ReactNode (required)
- `onChange`: (event: ChangeEvent<HTMLInputElement>) => void (required)
- `readOnly`: boolean
- `renderError`: (error: Error) => string
- `size`: "large" | "small"
- `textFieldProps`: ComponentPropsWithoutRef<"input">
- `value`: string

## DatePicker

**Import:** `import { DatePicker } from "./ld/DatePicker"`

- `locale`: string
- `a11yLabels`: DatePickerCalendarA11yLabels & { calendarIconButton: string }
- `disabled`: boolean
- `error`: ReactNode
- `format`: string
- `helperText`: ReactNode
- `id`: string
- `isOpen`: boolean
- `label`: ReactNode (required)
- `onClose`: () => void (required)
- `onOpen`: () => void (required)
- `onSelect`: (value: Date) => void (required)
- `readOnly`: boolean
- `renderError`: (error: DateFieldError, value: string) => string
- `size`: "large" | "small"
- `textFieldProps`: ComponentPropsWithRef<"input">
- `value`: Date
- `disabledDateFilter`: DatePickerDisabledDateFilterSignature
- `maxDate`: Date
- `minDate`: Date

## Divider

**Import:** `import { Divider } from "./ld/Divider"`

- `title`: string

## FocusTrap

**Import:** `import { FocusTrap } from "./ld/FocusTrap"`

- `children`: ReactNode (required)
- `hasFocusReturn`: boolean

## FormGroup

**Import:** `import { FormGroup } from "./ld/FormGroup"`

- `children`: ReactNode (required)
- `error`: ReactNode
- `helperText`: ReactNode
- `label`: ReactNode

## GridColumn

**Import:** `import { GridColumn } from "./ld/Grid"`

- `children`: ReactNode (required)
- `hasGutter`: boolean
- `lg`: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12
- `md`: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12
- `sm`: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12
- `xl`: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12
- `xxl`: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12

## Grid

**Import:** `import { Grid } from "./ld/Grid"`

- `children`: ReactNode (required)
- `hasGutter`: boolean

## IconButton

**Import:** `import { IconButton } from "./ld/IconButton"`

- `a11yLabel`: string
- `children`: ReactNode
- `color`: "default" | "white"
- `size`: "large" | "medium" | "small" | "xsmall"
- `variant`: "round" | "full"
- `href`: string (required)
- `disabled`: boolean

## Image

**Import:** `import { Image } from "./ld/Image"`

- `alt`: string
- `unsafeDecorative`: { reason: string }
- `src`: string

## LineClamp

**Import:** `import { LineClamp } from "./ld/LineClamp"`

- `children`: ReactNode (required)
- `lines`: number

## Link

**Import:** `import { Link } from "./ld/Link"`

- `children`: ReactNode (required)
- `color`: "default" | "subtle" | "white"
- `href`: string (required)
- `onClick`: (event: MouseEvent<HTMLAnchorElement>) => void
- `target`: string

## LinkButton

**Import:** `import { LinkButton } from "./ld/LinkButton"`

- `children`: ReactNode
- `color`: "default" | "subtle" | "white"
- `isFullWidth`: boolean
- `leading`: ReactNode
- `size`: "large" | "medium" | "small"
- `trailing`: ReactNode
- `href`: string (required)
- `disabled`: boolean
- `type`: "button" | "reset" | "submit"

## MagicBox

**Import:** `import { MagicBox } from "./ld/MagicBox"`

- `active`: boolean
- `borderRadius`: "25" | "50" | "100" | "200" | "round"
- `children`: ReactNode (required)
- `height`: CSSProperties["height"]
- `state`: "idle" | "loading" | "active"
- `width`: CSSProperties["width"]

## MenuItem

**Import:** `import { MenuItem } from "./ld/Menu"`

- `children`: ReactNode (required)
- `disabled`: boolean
- `leadingIcon`: ReactNode

## Menu

**Import:** `import { Menu } from "./ld/Menu"`

- `children`: ReactNode (required)
- `isOpen`: boolean
- `onClose`: (event: KeyboardEvent<HTMLElement> | MouseEvent<HTMLElement> | MouseEvent | PointerEvent | TouchEvent) => void (required)
- `onOpen`: (event: KeyboardEvent<HTMLElement> | MouseEvent<HTMLElement>) => void (required)
- `position`: "bottomLeft" | "bottomRight" | "topLeft" | "topRight"
- `trigger`: ReactElement (required)
- `triggerRef`: RefObject<HTMLElement> (required)

## Metric

**Import:** `import { Metric } from "./ld/Metric"`

- `a11yTrendIndicatorLabel`: string
- `textLabel`: ReactNode
- `timescope`: ReactNode
- `title`: ReactNode (required)
- `unit`: ReactNode
- `value`: ReactNode (required)
- `variant`: "negativeDown" | "negativeUp" | "neutral" | "positiveDown" | "positiveUp"

## Modal

**Import:** `import { Modal } from "./ld/Modal"`

- `actions`: ReactNode
- `children`: ReactNode (required)
- `closeButtonProps`: ModalCloseButtonProps
- `isOpen`: boolean (required)
- `onClose`: (event: ModalCloseEvent) => void (required)
- `onClosed`: () => void
- `size`: "small" | "medium" | "large"
- `title`: ReactNode (required)

## Nudge

**Import:** `import { Nudge } from "./ld/Nudge"`

- `actions`: ReactNode
- `children`: ReactNode (required)
- `closeButtonProps`: NudgeCloseButtonProps
- `leading`: ReactNode
- `onClose`: (event: MouseEvent<HTMLButtonElement>) => void
- `title`: ReactNode (required)

## Page

**Import:** `import { Page } from "./ld/Page"`

- `title`: string (required)
- `skipLinkLabel`: string
- `titleVisuallyHidden`: boolean
- `children`: ReactNode (required)

## Panel

**Import:** `import { Panel } from "./ld/Panel"`

- `actions`: ReactNode
- `children`: ReactNode (required)
- `closeButtonProps`: PanelCloseButtonProps
- `isOpen`: boolean (required)
- `onClose`: (event: PanelCloseEvent) => void (required)
- `onClosed`: () => void
- `position`: "left" | "right"
- `size`: "large" | "medium" | "small"
- `title`: ReactNode (required)

## Popover

**Import:** `import { Popover } from "./ld/Popover"`

- `children`: ReactElement (required)
- `isOpen`: boolean
- `a11yContentLabel`: string
- `basePopoverProps`: DetailedHTMLProps<ComponentPropsWithoutRef<"div">, HTMLDivElement>
- `content`: ReactNode (required)
- `hasNubbin`: boolean
- `onClose`: (event: MouseEvent<HTMLButtonElement, MouseEvent> | FocusEvent<HTMLDivElement> | PointerEvent | MouseEvent | TouchEvent | KeyboardEvent) => void (required)
- `position`: "bottomCenter" | "bottomLeft" | "bottomRight" | "left" | "right" | "topCenter" | "topLeft" | "topRight"
- `triggerRef`: RefObject<HTMLElement> (required)

## ProgressIndicator

**Import:** `import { ProgressIndicator } from "./ld/ProgressIndicator"`

- `a11yLabelledBy`: string
- `label`: ReactNode
- `max`: number
- `min`: number
- `value`: number
- `valueLabel`: string
- `variant`: "error" | "info" | "success" | "warning"

## ProgressTrackerItem

**Import:** `import { ProgressTrackerItem } from "./ld/ProgressTracker"`

- `a11yIndicatorLabel`: string
- `children`: ReactNode

## ProgressTracker

**Import:** `import { ProgressTracker } from "./ld/ProgressTracker"`

- `activeIndex`: number
- `children`: ReactNode
- `variant`: "error" | "info" | "success" | "warning"

## Radio

**Import:** `import { Radio } from "./ld/Radio"`

- `a11yLabelledBy`: string
- `label`: ReactNode
- `checked`: boolean
- `disabled`: boolean
- `id`: string
- `name`: string
- `onChange`: (event: ChangeEvent<HTMLInputElement>) => void
- `radioProps`: ComponentPropsWithoutRef<"input">
- `value`: number | string

## Rating

**Import:** `import { Rating } from "./ld/Rating"`

- `a11yLabel`: string
- `color`: "default" | "white"
- `count`: boolean
- `size`: "large" | "small"
- `value`: number

## Select

**Import:** `import { Select } from "./ld/Select"`

- `a11yMagicLabel`: string
- `children`: ReactNode (required)
- `disabled`: boolean
- `error`: ReactNode
- `helperText`: ReactNode
- `id`: string
- `isMagic`: boolean
- `label`: ReactNode (required)
- `leadingIcon`: ReactNode
- `onChange`: (event: ChangeEvent<HTMLSelectElement>) => void (required)
- `selectProps`: ComponentPropsWithoutRef<"select">
- `size`: "large" | "small"
- `value`: string

## SideNavigationItem

**Import:** `import { SideNavigationItem } from "./ld/SideNavigation"`

- `children`: ReactNode
- `href`: string (required)
- `isCurrent`: boolean
- `leading`: ReactNode
- `onClick`: (event: MouseEvent<HTMLAnchorElement>) => void
- `target`: string

## SideNavigation

**Import:** `import { SideNavigation } from "./ld/SideNavigation"`

- `children`: ReactNode

## Tree

**Import:** `import { Tree } from "./ld/SideNavigation"`

- `data`: TreeItemData[]
- `defaultExpandedIds`: string[]
- `onSelect`: (id: string) => void
- `selectedId`: string
- `label`: string
- `a11yLabelledBy`: string

## SkeletonText

**Import:** `import { SkeletonText } from "./ld/Skeleton"`

- `isMagic`: boolean
- `lines`: number

## Skeleton

**Import:** `import { Skeleton } from "./ld/Skeleton"`

- `height`: number | string
- `isMagic`: boolean
- `variant`: "rectangle" | "rounded"
- `width`: number | string

## Spinner

**Import:** `import { Spinner } from "./ld/Spinner"`

- `a11yLabel`: string
- `color`: "neutral" | "white"
- `size`: "large" | "small"
- `spinnerProps`: ComponentPropsWithoutRef<"svg">

## Switch

**Import:** `import { Switch } from "./ld/Switch"`

- `a11yLabelledBy`: string
- `label`: ReactNode
- `disabled`: boolean
- `isOn`: boolean
- `onClick`: (event: MouseEvent<HTMLButtonElement>) => void

## TabNavigationItem

**Import:** `import { TabNavigationItem } from "./ld/TabNavigation"`

- `children`: ReactNode (required)
- `href`: string (required)
- `isCurrent`: boolean
- `leadingIcon`: ReactNode
- `onClick`: (event: MouseEvent<HTMLAnchorElement>) => void
- `target`: string
- `trailing`: ReactNode

## TabNavigation

**Import:** `import { TabNavigation } from "./ld/TabNavigation"`

- `children`: ReactNode (required)

## Tag

**Import:** `import { Tag } from "./ld/Tag"`

- `children`: ReactNode (required)
- `color`: "blue" | "brand" | "cyan" | "edited" | "gray" | "green" | "info" | "negative" | "orange" | "pink" | "positive" | "purple" | "red" | "spark" | "teal" | "warning" | "yellow"
- `leading`: ReactNode
- `variant`: "primary" | "secondary" | "tertiary"

## TextArea

**Import:** `import { TextArea } from "./ld/TextArea"`

- `a11yMagicLabel`: string
- `disabled`: boolean
- `error`: ReactNode
- `helperText`: ReactNode
- `id`: string
- `isMagic`: boolean
- `label`: ReactNode (required)
- `maxLength`: number
- `maxLengthA11yAnnouncement`: string
- `onChange`: (event: ChangeEvent<HTMLTextAreaElement>) => void (required)
- `readOnly`: boolean
- `size`: "large" | "small"
- `textAreaProps`: ComponentPropsWithoutRef<"textarea">
- `value`: string

## TextField

**Import:** `import { TextField } from "./ld/TextField"`

- `a11yMagicLabel`: string
- `disabled`: boolean
- `error`: ReactNode
- `helperText`: ReactNode
- `id`: string
- `isMagic`: boolean
- `label`: ReactNode (required)
- `leadingIcon`: ReactNode
- `onChange`: (event: ChangeEvent<HTMLInputElement>) => void (required)
- `readOnly`: boolean
- `size`: "large" | "small"
- `textFieldProps`: ComponentPropsWithoutRef<"input">
- `trailing`: ReactNode
- `type`: "email" | "number" | "password" | "search" | "tel" | "text" | "time" | "url"
- `value`: string

## WCPBasicBanner

**Import:** `import { WCPBasicBanner } from "./ld/WCPBasicBanner"`

- `icon`: ReactNode
- `text`: string
- `variant`: "default" | "brand" | "inverse"
- `onClick`: () => void

## WCPButtonGroup

**Import:** `import { WCPButtonGroup } from "./ld/WCPButtonGroup"`

- `layout`: "inline" | "stacked"
- `pattern`: "primary-secondary" | "primary-tertiary" | "secondary-tertiary" | "tertiary-tertiary" | "three-options"
- `preferredLabel`: string
- `alternateLabel`: string
- `thirdLabel`: string
- `preferredRight`: boolean
- `fullWidth`: boolean
- `onPreferred`: MouseEventHandler<HTMLButtonElement>
- `onAlternate`: MouseEventHandler<HTMLButtonElement>
- `onThird`: MouseEventHandler<HTMLButtonElement>
- `preferredButtonProps`: Omit<ComponentPropsWithoutRef<"button">, "onClick" | "children">
- `alternateButtonProps`: Omit<ComponentPropsWithoutRef<"button">, "onClick" | "children">
- `thirdButtonProps`: Omit<ComponentPropsWithoutRef<"button">, "onClick" | "children">

## WCPCarouselProductCard

**Import:** `import { WCPCarouselProductCard } from "./ld/WCPCarouselProductCard"`

- `image`: string (required)
- `price`: string (required)
- `cents`: string (required)
- `onAddToCart`: () => void
- `cartQty`: number
- `onCartQtyChange`: (qty: number) => void

## WCPCountryCodePhoneInput

**Import:** `import { WCPCountryCodePhoneInput } from "./ld/WCPCountryCodePhoneInput"`

- `label`: string
- `value`: string
- `onChange`: (value: string) => void
- `selectedCountry`: WCPCountry
- `onCountryChange`: (country: WCPCountry) => void
- `countries`: WCPCountry[]
- `disabled`: boolean
- `readOnly`: boolean
- `error`: boolean
- `helperText`: string
- `errorText`: string
- `placeholder`: string
- `id`: string

## WCPCountrySelectBottomSheet

**Import:** `import { WCPCountrySelectBottomSheet } from "./ld/WCPCountrySelectBottomSheet"`

- `countries`: WCPCountry[]
- `value`: string
- `onSelect`: (country: WCPCountry) => void
- `showDialCode`: boolean
- `variant`: "flat" | "slot"
- `title`: string
- `actionLabel`: string
- `onConfirm`: (selected: WCPCountry | undefined) => void
- `onClose`: () => void
- `open`: boolean (required)

## WCPCountrySelectDropdown

**Import:** `import { WCPCountrySelectDropdown } from "./ld/WCPCountrySelectDropdown"`

- `countries`: WCPCountry[]
- `mode`: "single" | "multi"
- `value`: string | string[]
- `onChange`: (value: string | string[], countries: WCPCountry | WCPCountry[]) => void
- `placeholder`: string
- `showDialCode`: boolean
- `confirmLabel`: string
- `label`: string
- `disabled`: boolean
- `triggerWidth`: string | number

## WCPCountrySelectGroup

**Import:** `import { WCPCountrySelectGroup } from "./ld/WCPCountrySelectGroup"`

- `countries`: WCPCountry[]
- `value`: string
- `onChange`: (country: WCPCountry) => void
- `description`: string
- `footerText`: string
- `showDialCode`: boolean

## WCPFlag

**Import:** `import { WCPFlag } from "./ld/WCPFlag"`

- `label`: string
- `variant`: "holiday-restricted" | "brand-subtle" | "scarcity" | "savings-bold" | "savings-subtle" | "confidence-subtle" | "confidence-bold" | "confidence-alt" | "confidence" | "holiday-member" | "social" | "urgent"
- `leadingIcon`: ReactNode
- `trailingIcon`: ReactNode

## WCPFloatingButton

**Import:** `import { WCPFloatingButton } from "./ld/WCPFloatingButton"`

- `children`: ReactNode (required)
- `size`: "xsmall" | "small" | "medium" | "large"
- `'aria-label'`: string (required)

## WCPHeader

**Import:** `import { WCPHeader } from "./ld/WCPHeader"`

- `cartCount`: number
- `cartPrice`: string
- `mobileVariant`: "classic" | "topnav-blue" | "topnav-white"
- `showMobileSubNav`: boolean
- `showMobileDeliveryBanner`: boolean

## WCPHeartView

**Import:** `import { WCPHeartView } from "./ld/WCPHeartView"`

- `activated`: boolean
- `defaultActivated`: boolean
- `onChange`: (activated: boolean) => void
- `size`: "small" | "medium"
- `listName`: string
- `onViewList`: () => void
- `onSnackbar`: (message: string, actionLabel: string, onAction: () => void) => void
- `snackbarDuration`: number
- `disabled`: boolean
- `'aria-label'`: string
- `calloutPosition`: "left" | "right" | "bottom" | "top"

## WCPItemTile

**Import:** `import { WCPItemTile } from "./ld/WCPItemTile"`

- `image`: string (required)
- `name`: string (required)
- `price`: string (required)
- `cents`: string (required)
- `originalPrice`: string
- `pricePrefix`: string
- `priceSuffix`: string
- `badge`: { label: string; type: "bestseller" | "deal" | "popular" | "rollback" | "clearance"; ... }
- `hearted`: boolean
- `onHeartChange`: (hearted: boolean) => void

## WCPNewArrivalsCarousel

**Import:** `import { WCPNewArrivalsCarousel } from "./ld/WCPNewArrivalsCarousel"`

- `slides`: CarouselSlide[]

## WCPOrderCard

**Import:** `import { WCPOrderCard } from "./ld/WCPOrderCard"`

- `orderType`: "curbside" | "delivery" | "shipping" | "store" | "auto" (required)
- `location`: string
- `seller`: string
- `fulfilledBy`: string
- `statusHeading`: string (required)
- `timelineStep`: "placed" | "preparing" | "on-the-way" | "delivered"
- `timelineVariant`: "delivery" | "pickup"
- `isDelayed`: boolean
- `products`: OrderProduct[] (required)
- `actions`: OrderAction[]
- `orderTotal`: string
- `showStartReturn`: boolean
- `returnNotice`: string
- `returnDeadline`: string
- `addItemsBanner`: string
- `serviceDetails`: ServiceDetails

## WCPQueueBanner

**Import:** `import { WCPQueueBanner } from "./ld/WCPQueueBanner"`

- `variant`: "lineJoined" | "warning" | "checkout" | "error" (required)
- `timeDisplay`: string
- `endTime`: Date | number | string
- `message`: string
- `snackbarText`: string
- `productImage`: string
- `onView`: () => void
- `onLeave`: () => void
- `onClose`: () => void
- `onAction`: () => void
- `inline`: boolean

## WCPQueueCard

**Import:** `import { WCPQueueCard } from "./ld/WCPQueueCard"`

- `image`: string
- `description`: string
- `price`: string (required)
- `originalPrice`: string
- `timeDisplay`: string
- `endTime`: Date | number | string
- `timerVariant`: TimerViewVariant
- `timerLabel`: string
- `productImageAlt`: string

## WCPQueueItemCard

**Import:** `import { WCPQueueItemCard } from "./ld/WCPQueueItemCard"`

- `item`: QueueItem (required)

## WCPQueueLanding

**Import:** `import { WCPQueueLanding } from "./ld/WCPQueueLanding"`

- `variant`: "authenticated" | "unauthenticated"
- `product`: QueueLandingProduct (required)
- `timeDisplay`: string
- `endTime`: Date | number | string
- `timerVariant`: TimerViewVariant
- `onSignIn`: () => void

## WCPQueuePanel

**Import:** `import { WCPQueuePanel } from "./ld/WCPQueuePanel"`

- `isOpen`: boolean (required)
- `onClose`: () => void (required)
- `items`: QueueItem[] (required)

## WCPRating

**Import:** `import { WCPRating } from "./ld/WCPRating"`

- `value`: number
- `defaultValue`: number
- `onChange`: (value: number) => void
- `size`: "small" | "medium"
- `disabled`: boolean
- `'aria-label'`: string

## WCPRatingDisplay

**Import:** `import { WCPRatingDisplay } from "./ld/WCPRatingDisplay"`

- `value`: number
- `size`: "small" | "medium"
- `color`: "default" | "inverse"
- `count`: string
- `linkText`: string
- `linkHref`: string
- `onLinkClick`: (e: MouseEvent) => void
- `text`: string
- `'aria-label'`: string

## WCPRichMediaSheet

**Import:** `import { WCPRichMediaSheet } from "./ld/WCPRichMediaSheet"`

- `isOpen`: boolean (required)
- `onClose`: () => void (required)
- `headerVariant`: "title" | "title-subtitle" | "logo-left" | "logo-center" | "inverse" | "none"
- `title`: string
- `subtitle`: string
- `logoSlot`: ReactNode
- `surfaceVariant`: "default" | "brand" | "brand-bold" | "media"
- `children`: ReactNode (required)
- `actions`: ReactNode
- `showFooterDivider`: boolean
- `adjustHeight`: "fixed" | "content"
- `ariaLabel`: string

## WCPRichSnackbar

**Import:** `import { WCPRichSnackbar } from "./ld/WCPRichSnackbar"`

- `open`: boolean
- `color`: "primary" | "secondary" | "inverse" | "brand"
- `contentVariant`: "left-regular" | "left-bold" | "center-regular" | "center-bold"
- `leadingSlot`: ReactNode
- `message`: string | ReactNode (required)
- `actionLabel`: string
- `onAction`: () => void
- `onClose`: () => void
- `duration`: number
- `position`: "bottom-left" | "bottom-center" | "bottom-right"
- `inline`: boolean

## WCPSearchBar

**Import:** `import { WCPSearchBar } from "./ld/WCPSearchBar"`

- `value`: string (required)
- `onChange`: (value: string) => void (required)
- `onClear`: () => void
- `onCancel`: () => void
- `placeholder`: string
- `disabled`: boolean

## WCPSignatureCapture

**Import:** `import { WCPSignatureCapture } from "./ld/WCPSignatureCapture"`

- `variant`: "trigger" | "terms" | "base" | "reauth" (required)
- `userName`: string
- `signatureState`: "unsigned" | "signed" | "signed-as"
- `signedName`: string
- `onAgreeAndSign`: () => void
- `onChangeSignature`: () => void
- `onRefreshPage`: () => void
- `onConfirm`: () => void
- `subText`: string
- `title`: string
- `showPreviewWarning`: boolean
- `showTechError`: boolean
- `showPetNameWarning`: boolean
- `showSignBeforeSubmitError`: boolean
- `showPreviewBeforeSignError`: boolean
- `showCheckboxError`: boolean
- `fullName`: string
- `onFullNameChange`: (name: string) => void
- `onPreviewSignature`: () => void
- `isSignChecked`: boolean
- `onSignCheckedChange`: (checked: boolean) => void
- `reauthSubVariant`: "agree-sign" | "signed" | "signed-as"
- `showReauthError`: boolean

## WCPSignatureCaptureBottomSheet

**Import:** `import { WCPSignatureCaptureBottomSheet } from "./ld/WCPSignatureCaptureBottomSheet"`

- `isOpen`: boolean (required)
- `onClose`: () => void (required)
- `title`: string
- `onSubmit`: () => void
- `submitLabel`: string
- `submitDisabled`: boolean

## WCPSignatureCapturePanel

**Import:** `import { WCPSignatureCapturePanel } from "./ld/WCPSignatureCapturePanel"`

- `isOpen`: boolean (required)
- `onClose`: () => void (required)
- `title`: string
- `size`: "small" | "medium" | "large"
- `position`: "left" | "right"
- `onSubmit`: () => void
- `submitLabel`: string

## WCPTimerView

**Import:** `import { WCPTimerView } from "./ld/WCPTimerView"`

- `timeDisplay`: string
- `variant`: "waiting" | "warning" | "expiring" | "badge"
- `size`: "medium" | "small"
- `endTime`: Date | number | string
- `badgeColor`: "blue" | "spark" | "negative"
- `label`: string
- `showLabel`: boolean

## WCPUploadImage

**Import:** `import { WCPUploadImage } from "./ld/WCPUploadImage"`

- `images`: UploadedImage[]
- `onChange`: (images: UploadedImage[]) => void
- `maxImages`: number
- `invalid`: boolean
- `errorMessage`: string
- `photoTip`: string
- `label`: string
- `subLabel`: string

## Accordion

**Import:** `import { Accordion } from "./ld/Accordion"`

- `children`: ReactNode (required)
- `collapsible`: boolean
- `defaultOpenItems`: Array<string | number>
- `multiple`: boolean
- `onToggle`: (openItems: Array<string | number>) => void
- `openItems`: Array<string | number>

## AccordionItem

**Import:** `import { AccordionItem } from "./ld/Accordion"`

- `children`: ReactNode (required)
- `value`: string | number (required)

## AccordionHeader

**Import:** `import { AccordionHeader } from "./ld/Accordion"`

- `children`: ReactNode (required)

## AccordionPanel

**Import:** `import { AccordionPanel } from "./ld/Accordion"`

- `children`: ReactNode (required)

## AlertDialog

**Import:** `import { AlertDialog } from "./ld/AlertDialog"`

- `open`: boolean
- `defaultOpen`: boolean
- `onOpenChange`: (open: boolean) => void
- `children`: ReactNode (required)

## AlertDialogTrigger

**Import:** `import { AlertDialogTrigger } from "./ld/AlertDialog"`

- `asChild`: boolean

## AlertDialogContent

**Import:** `import { AlertDialogContent } from "./ld/AlertDialog"`

- `children`: ReactNode (required)
- `title`: ReactNode (required)
- `actions`: ReactNode
- `size`: ModalSize

## AlertDialogAction

**Import:** `import { AlertDialogAction } from "./ld/AlertDialog"`

- `variant`: "primary" | "destructive"

## Avatar

**Import:** `import { Avatar } from "./ld/Avatar"`

- `a11yLabel`: string
- `a11yLabelledBy`: string
- `color`: "brand" | "neutral"
- `icon`: ReactNode
- `image`: { src: string; alt?: string }
- `name`: string
- `shape`: "circular" | "square"
- `size`: "xs" | "small" | "medium" | "large" | "xl"

## Carousel

**Import:** `import { Carousel } from "./ld/Carousel"`

- `children`: ReactNode (required)
- `orientation`: "horizontal" | "vertical"

## CarouselContent

**Import:** `import { CarouselContent } from "./ld/Carousel"`

- `children`: ReactNode (required)

## CarouselItem

**Import:** `import { CarouselItem } from "./ld/Carousel"`

- `children`: ReactNode (required)

## CarouselProgressBar

**Import:** `import { CarouselProgressBar } from "./ld/Carousel"`

- `autoPlay`: boolean
- `autoPlayInterval`: number
- `showDots`: boolean

## CategoryNav

**Import:** `import { CategoryNav } from "./ld/CategoryNav"`

- `items`: CategoryNavItem[]
- `activeItem`: string
- `onItemClick`: (label: string) => void
- `onBrowseClick`: () => void
- `browseHref`: string

## FluentCombobox

**Import:** `import { FluentCombobox } from "./ld/Combobox"`

- `label`: string
- `a11yLabelledBy`: string
- `disabled`: boolean
- `onChange`: (value: string) => void
- `options`: ComboboxOption[]
- `placeholder`: string
- `selectedValue`: string
- `value`: string

## Command

**Import:** `import { Command } from "./ld/Command"`

- `children`: ReactNode (required)
- `onSelect`: (value: string) => void

## CommandList

**Import:** `import { CommandList } from "./ld/Command"`

- `children`: ReactNode (required)

## CommandEmpty

**Import:** `import { CommandEmpty } from "./ld/Command"`

- `children`: ReactNode (required)

## CommandGroup

**Import:** `import { CommandGroup } from "./ld/Command"`

- `children`: ReactNode (required)
- `heading`: string

## CommandItem

**Import:** `import { CommandItem } from "./ld/Command"`

- `children`: ReactNode (required)
- `value`: string
- `disabled`: boolean
- `onSelect`: () => void

## CommandDialog

**Import:** `import { CommandDialog } from "./ld/Command"`

- `children`: ReactNode (required)
- `open`: boolean
- `onOpenChange`: (open: boolean) => void

## ContentCard

**Import:** `import { ContentCard } from "./ld/ContentCard"`

- `imageSrc`: string (required)
- `imageAlt`: string (required)
- `eyebrow`: string
- `headline`: string (required)
- `subtext`: string
- `ctaLabel`: string
- `ctaHref`: string
- `onClick`: () => void
- `variant`: "vertical" | "horizontal" | "background"

## DropdownMenu

**Import:** `import { DropdownMenu } from "./ld/DropdownMenu"`

- `open`: boolean
- `defaultOpen`: boolean
- `onOpenChange`: (open: boolean) => void
- `children`: ReactNode (required)
- `trigger`: "click" | "context-menu"

## DropdownMenuTrigger

**Import:** `import { DropdownMenuTrigger } from "./ld/DropdownMenu"`

- `children`: ReactNode (required)
- `asChild`: boolean
- `onClick`: (e: MouseEvent) => void

## DropdownMenuRadioGroup

**Import:** `import { DropdownMenuRadioGroup } from "./ld/DropdownMenu"`

- `value`: string
- `onValueChange`: (value: string) => void
- `children`: ReactNode

## DropdownMenuSubTrigger

**Import:** `import { DropdownMenuSubTrigger } from "./ld/DropdownMenu"`

- `inset`: boolean
- `children`: ReactNode

## DropdownMenuSubContent

**Import:** `import { DropdownMenuSubContent } from "./ld/DropdownMenu"`

- `children`: ReactNode

## DropdownMenuContent

**Import:** `import { DropdownMenuContent } from "./ld/DropdownMenu"`

- `sideOffset`: number
- `side`: "top" | "bottom" | "left" | "right"
- `align`: "start" | "center" | "end"
- `children`: ReactNode

## DropdownMenuItem

**Import:** `import { DropdownMenuItem } from "./ld/DropdownMenu"`

- `inset`: boolean
- `disabled`: boolean
- `onSelect`: () => void
- `children`: ReactNode

## DropdownMenuCheckboxItem

**Import:** `import { DropdownMenuCheckboxItem } from "./ld/DropdownMenu"`

- `checked`: boolean
- `onCheckedChange`: (checked: boolean) => void
- `disabled`: boolean
- `children`: ReactNode

## DropdownMenuRadioItem

**Import:** `import { DropdownMenuRadioItem } from "./ld/DropdownMenu"`

- `value`: string (required)
- `disabled`: boolean
- `children`: ReactNode

## DropdownMenuLabel

**Import:** `import { DropdownMenuLabel } from "./ld/DropdownMenu"`

- `inset`: boolean
- `children`: ReactNode

## DropdownMenuShortcut

**Import:** `import { DropdownMenuShortcut } from "./ld/DropdownMenu"`

- `children`: ReactNode

## FluentMenu

**Import:** `import { FluentMenu } from "./ld/FluentMenu"`

- `children`: ReactNode (required)
- `open`: boolean
- `onOpenChange`: (open: boolean) => void

## FluentMenuTrigger

**Import:** `import { FluentMenuTrigger } from "./ld/FluentMenu"`

- `children`: ReactElement (required)

## FluentMenuList

**Import:** `import { FluentMenuList } from "./ld/FluentMenu"`

- `children`: ReactNode (required)

## FluentMenuItem

**Import:** `import { FluentMenuItem } from "./ld/FluentMenu"`

- `children`: ReactNode (required)
- `disabled`: boolean
- `icon`: ReactNode

## Pagination

**Import:** `import { Pagination } from "./ld/Pagination"`

- `children`: ReactNode

## PaginationContent

**Import:** `import { PaginationContent } from "./ld/Pagination"`

- `children`: ReactNode

## PaginationItem

**Import:** `import { PaginationItem } from "./ld/Pagination"`

- `children`: ReactNode

## PaginationLink

**Import:** `import { PaginationLink } from "./ld/Pagination"`

- `isActive`: boolean
- `href`: string
- `onClick`: MouseEventHandler<HTMLAnchorElement>
- `children`: ReactNode

## PaginationPrevious

**Import:** `import { PaginationPrevious } from "./ld/Pagination"`

- `href`: string
- `onClick`: MouseEventHandler<HTMLAnchorElement>

## PaginationNext

**Import:** `import { PaginationNext } from "./ld/Pagination"`

- `href`: string
- `onClick`: MouseEventHandler<HTMLAnchorElement>

## PaginationEllipsis

**Import:** `import { PaginationEllipsis } from "./ld/Pagination"`

- `children`: ReactNode

## QuantityStepper

**Import:** `import { QuantityStepper } from "./ld/QuantityStepper"`

- `variant`: "primary" | "secondary" | "tertiary"
- `size`: "small" | "medium" | "large"
- `count`: number
- `defaultCount`: number
- `maxQuantity`: number
- `addLabel`: string
- `showAddLabel`: boolean
- `cartLabel`: string
- `countLabel`: string
- `disabled`: boolean
- `showTrashOnRemove`: boolean
- `onChange`: (count: number) => void

## ScrollArea

**Import:** `import { ScrollArea } from "./ld/ScrollArea"`

- `children`: ReactNode (required)

## ScrollBar

**Import:** `import { ScrollBar } from "./ld/ScrollArea"`

- `orientation`: "vertical" | "horizontal"

## SectionHeader

**Import:** `import { SectionHeader } from "./ld/SectionHeader"`

- `title`: string (required)
- `subtitle`: string
- `actionLabel`: string
- `actionHref`: string
- `onAction`: () => void
- `headingLevel`: "h2" | "h3" | "h4"

## SegmentedControl

**Import:** `import { SegmentedControl } from "./ld/SegmentedControl"`

- `items`: SegmentedControlItem[] (required)
- `value`: string (required)
- `onChange`: (value: string) => void (required)
- `'aria-label'`: string
- `disabled`: boolean
- `isFullWidth`: boolean

## Form

**Import:** `import { Form } from "./ld/SharedForm"`

- `children`: ReactNode (required)
- `onSubmit`: (values: Record<string, string>, event: FormEvent<HTMLFormElement>) => void

## FormField

**Import:** `import { FormField } from "./ld/SharedForm"`

- `children`: ReactNode (required)
- `name`: string (required)
- `rules`: ValidationRules

## FormItem

**Import:** `import { FormItem } from "./ld/SharedForm"`

- `children`: ReactNode (required)

## SharedFormLabel

**Import:** `import { SharedFormLabel } from "./ld/SharedForm"`

- `children`: ReactNode (required)
- `disabled`: boolean

## FormControl

**Import:** `import { FormControl } from "./ld/SharedForm"`

- `children`: ReactNode (required)

## FormDescription

**Import:** `import { FormDescription } from "./ld/SharedForm"`

- `children`: ReactNode (required)

## FormMessage

**Import:** `import { FormMessage } from "./ld/SharedForm"`

- `children`: ReactNode

## Slider

**Import:** `import { Slider } from "./ld/Slider"`

- `min`: number
- `max`: number
- `step`: number
- `value`: number[]
- `defaultValue`: number[]
- `onValueChange`: (value: number[]) => void
- `disabled`: boolean
- `orientation`: "horizontal" | "vertical"
- `name`: string

## SpinButton

**Import:** `import { SpinButton } from "./ld/SpinButton"`

- `label`: string
- `a11yLabelledBy`: string
- `disabled`: boolean
- `max`: number
- `min`: number
- `onChange`: (value: number) => void
- `step`: number
- `value`: number

## Toggle

**Import:** `import { Toggle } from "./ld/Toggle"`

- `pressed`: boolean
- `defaultPressed`: boolean
- `onPressedChange`: (pressed: boolean) => void
- `variant`: "default" | "outline"
- `size`: "small" | "medium" | "large"
- `shape`: "square" | "rounded"

## Tooltip

**Import:** `import { Tooltip } from "./ld/Tooltip"`

- `children`: ReactElement (required)
- `content`: string (required)
- `position`: "above" | "below" | "before" | "after"
- `relationship`: "label" | "description"
- `showDelay`: number
- `hideDelay`: number
